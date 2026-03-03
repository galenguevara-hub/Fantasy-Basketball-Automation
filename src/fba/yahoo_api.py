"""
Yahoo Fantasy Basketball API Client

Replaces the Playwright-based scraper with direct Yahoo Fantasy API calls.
Produces the same standings.json format consumed by normalize.py and the rest of the app.
Still includes a legacy file-based OAuth fallback for archived manual tools.
"""

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import Game

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
OAUTH_FILE = _DATA_DIR / "oauth2.json"
STANDINGS_FILE = _DATA_DIR / "standings.json"

# Yahoo stat_id → display name mapping for NBA
STAT_ID_MAP = {
    0: "GP",
    5: "FG%",
    8: "FT%",
    10: "3PTM",
    12: "PTS",
    15: "REB",
    16: "AST",
    17: "ST",
    18: "BLK",
}

# The 8 roto scoring categories (higher is always better)
ROTO_CATEGORIES = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK"]


class YahooAPIError(Exception):
    """Raised when the Yahoo API returns an error or is unreachable."""
    pass


class AuthError(YahooAPIError):
    """Raised when OAuth credentials are missing or expired."""
    pass


def get_oauth_session() -> OAuth2:
    """Create and return a valid OAuth2 session for the legacy file-based flow.

    Raises AuthError if credentials file is missing or token cannot be refreshed.
    """
    if not OAUTH_FILE.exists():
        raise AuthError(
            "No OAuth credentials found. Use legacy/oauth_setup.py to authorize with Yahoo."
        )

    try:
        oauth = OAuth2(None, None, from_file=str(OAUTH_FILE))
    except Exception as e:
        raise AuthError(f"Failed to load OAuth credentials: {e}")

    if not oauth.token_is_valid():
        try:
            oauth.refresh_access_token()
        except Exception as e:
            raise AuthError(
                f"OAuth token expired and could not be refreshed: {e}. "
                "Run legacy/oauth_setup.py to re-authorize."
            )

    return oauth


def get_oauth_session_from_tokens(access_token: str, refresh_token: str) -> OAuth2:
    """Build a yahoo_oauth OAuth2 session from token values (no credentials file needed).

    Writes a temporary JSON file (deleted immediately after OAuth2 loads it) so
    yahoo_oauth can initialise its internal OAuth2Session without a permanent file.
    The caller is responsible for passing a still-valid access_token so that
    yahoo_oauth does not attempt a mid-request refresh (which would fail because
    the temp file is gone).
    """
    from fba.config import Config  # local import avoids circular dependency at module level

    token_data = {
        "consumer_key": Config.YAHOO_CLIENT_ID,
        "consumer_secret": Config.YAHOO_CLIENT_SECRET,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_time": time.time(),
        "token_type": "bearer",
        "expires_in": 3600,  # tell yahoo_oauth this token is valid so it doesn't re-auth via stdin
    }

    fd, temp_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(token_data, f)
        oauth = OAuth2(None, None, from_file=temp_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    return oauth


def is_authenticated() -> bool:
    """Check if valid legacy file-based OAuth credentials exist."""
    if not OAUTH_FILE.exists():
        return False
    try:
        oauth = OAuth2(None, None, from_file=str(OAUTH_FILE))
        return oauth.token_is_valid()
    except Exception:
        return False


def _get_team_stats_raw(session, team_key: str) -> dict:
    """Fetch full stats for a team via the raw Yahoo API.

    Returns dict mapping stat display name to value (e.g., {"GP": 666, "FG%": 0.476, ...}).
    Uses the team stats endpoint which includes GP (stat_id 0) that the library filters out.
    """
    url = (
        f"https://fantasysports.yahooapis.com/fantasy/v2"
        f"/team/{team_key}/stats?format=json"
    )
    resp = session.get(url)
    if resp.status_code != 200:
        raise YahooAPIError(
            f"Failed to fetch stats for team {team_key}: HTTP {resp.status_code}"
        )

    data = resp.json()
    team_data = data["fantasy_content"]["team"]
    raw_stats = team_data[1]["team_stats"]["stats"]

    stats = {}
    for entry in raw_stats:
        stat_id = entry["stat"]["stat_id"]
        value = entry["stat"]["value"]

        # stat_id can be int or str depending on position in response
        stat_id_int = int(stat_id) if isinstance(stat_id, str) else stat_id

        if stat_id_int in STAT_ID_MAP:
            name = STAT_ID_MAP[stat_id_int]
            # Convert to appropriate type
            if name in ("FG%", "FT%"):
                stats[name] = float(value) if value else 0.0
            elif name == "GP":
                stats[name] = int(value) if value else 0
            else:
                stats[name] = int(float(value)) if value else 0

    return stats


def compute_roto_points(teams_data: list[dict]) -> dict:
    """Compute per-category roto points for each team.

    In roto scoring, teams are ranked 1-N in each category.
    Highest value gets N points, lowest gets 1. Ties get averaged ranks.

    Args:
        teams_data: List of dicts with "team_name" and "stats" keys.

    Returns:
        Dict mapping team_name → {category: roto_points}.
    """
    n = len(teams_data)
    roto = {t["team_name"]: {} for t in teams_data}

    for cat in ROTO_CATEGORIES:
        # Collect (value, team_name) pairs, skip teams with missing data
        entries = []
        for t in teams_data:
            val = t["stats"].get(cat)
            if val is not None:
                entries.append((float(val), t["team_name"]))

        # Sort ascending (lowest value = lowest rank = fewest roto points)
        entries.sort(key=lambda x: (x[0], x[1]))

        # Assign ranks with tie averaging
        i = 0
        while i < len(entries):
            # Find all teams tied at this value
            j = i
            while j < len(entries) and entries[j][0] == entries[i][0]:
                j += 1

            # Average rank for tied teams (1-indexed)
            avg_rank = sum(range(i + 1, j + 1)) / (j - i)

            for k in range(i, j):
                team_name = entries[k][1]
                # Roto points = rank (1..N where N=best)
                roto[team_name][cat] = avg_rank if avg_rank != int(avg_rank) else int(avg_rank)

            i = j

        # Teams with missing data get rank 1 (worst)
        for t in teams_data:
            if cat not in roto[t["team_name"]]:
                roto[t["team_name"]][cat] = 1

    return roto


def fetch_standings(league_id: str, oauth: Optional[OAuth2] = None) -> dict:
    """Fetch league standings from Yahoo Fantasy API.

    Args:
        league_id: The numeric league ID (e.g., "47205").
        oauth: Optional pre-built OAuth2 session. If not provided, falls back to
               the file-based session (legacy single-user mode).

    Returns:
        Dict in the exact standings.json format consumed by the rest of the app.

    Raises:
        AuthError: If OAuth credentials are missing or expired.
        YahooAPIError: If the API returns an error.
    """
    if oauth is None:
        oauth = get_oauth_session()
    game = Game(oauth, "nba")
    game_id = game.game_id()

    full_league_id = f"{game_id}.l.{league_id}"
    logger.info(f"Fetching standings for league {full_league_id}...")

    league = game.to_league(full_league_id)

    # Get standings (rank, team name, total points)
    standings = league.standings()

    # Get stat categories from the league
    stat_cats = league.stat_categories()
    categories = [cat["display_name"] for cat in stat_cats]

    # Fetch full stats for each team (including GP via raw API)
    teams_data = []
    for team_info in standings:
        team_key = team_info["team_key"]
        team_name = team_info["name"]
        rank = int(team_info["rank"])
        total_points = float(team_info.get("points_for", 0))
        pts_change_raw = team_info.get("points_change", 0)
        try:
            pts_change = int(float(pts_change_raw))
        except (ValueError, TypeError):
            pts_change = 0

        logger.info(f"  Fetching stats for {team_name}...")
        stats = _get_team_stats_raw(oauth.session, team_key)

        teams_data.append({
            "team_key": team_key,
            "team_name": team_name,
            "rank": rank,
            "total_points": total_points,
            "pts_change": pts_change,
            "stats": stats,
        })

    # Compute per-category roto points
    roto = compute_roto_points(teams_data)

    # Build final output matching standings.json format
    teams = []
    for t in teams_data:
        team_roto = roto[t["team_name"]]

        teams.append({
            "rank": t["rank"],
            "team_name": t["team_name"],
            "total_points": t["total_points"],
            "pts_change": t["pts_change"],
            "roto_points": team_roto,
            "stats": t["stats"],
        })

    # Sort by rank
    teams.sort(key=lambda t: t["rank"])

    result = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "league": {"categories": [{"display_name": cat} for cat in categories]},
        "teams": teams,
    }

    # Validation: check that computed roto points sum matches API total
    for t in teams:
        computed_total = sum(
            v for v in t["roto_points"].values() if isinstance(v, (int, float))
        )
        if abs(computed_total - t["total_points"]) > 0.5:
            logger.warning(
                f"Roto points mismatch for {t['team_name']}: "
                f"computed={computed_total}, API={t['total_points']}"
            )

    return result


def fetch_and_save(league_id: str) -> dict:
    """Fetch standings and save to disk.

    Returns the standings data dict.
    """
    data = fetch_standings(league_id)

    STANDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STANDINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    teams_count = len(data.get("teams", []))
    logger.info(f"Saved standings for {teams_count} teams to {STANDINGS_FILE}")

    return data
