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

from typing import List

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from yahoo_oauth import OAuth2
from yahoo_fantasy_api import Game

from fba.category_config import (
    CategoryConfig,
    KNOWN_STATS,
    DEFAULT_8CAT_CONFIG,
    build_category_config_from_raw,
    build_stat_id_map,
    to_serializable,
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
OAUTH_FILE = _DATA_DIR / "oauth2.json"
STANDINGS_FILE = _DATA_DIR / "standings.json"

# Legacy compat: flat stat_id → display name mapping (used by tests and
# as fallback when no dynamic config is available).
STAT_ID_MAP = {sid: meta["key"] for sid, meta in KNOWN_STATS.items()}

# Legacy compat: 8-cat roto list (replaced by dynamic config at runtime).
ROTO_CATEGORIES = [c.key for c in DEFAULT_8CAT_CONFIG]


def _configure_session_retries(session) -> None:
    """Mount a retry adapter on a requests.Session.

    Retries up to 3 times on connection-level failures (including transient DNS
    errors like EAI_AGAIN that occur on Fly.io cold-start machine wake-ups).
    Backoff: 1s → 2s → 4s between attempts.
    """
    retry = Retry(
        total=3,
        connect=3,
        backoff_factor=1,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)


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


def _get_team_stats_raw(
    session,
    team_key: str,
    stat_id_configs: Optional[dict[int, CategoryConfig]] = None,
) -> dict:
    """Fetch full stats for a team via the raw Yahoo API.

    Returns dict mapping stat canonical key to value (e.g., {"GP": 666, "FG%": 0.476, ...}).
    Uses the team stats endpoint which includes GP (stat_id 0) that the library filters out.

    Args:
        session: Authenticated requests session.
        team_key: Yahoo team key string.
        stat_id_configs: Optional {stat_id: CategoryConfig} map. When provided,
            only stats matching these IDs are ingested (plus GP=0).
            Falls back to the legacy STAT_ID_MAP when None.
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

    # Build the set of stat_ids to ingest (scoring categories + GP)
    if stat_id_configs is not None:
        allowed_ids = set(stat_id_configs.keys()) | {0}  # always include GP
    else:
        allowed_ids = set(STAT_ID_MAP.keys())

    stats = {}
    for entry in raw_stats:
        stat_id = entry["stat"]["stat_id"]
        value = entry["stat"]["value"]

        stat_id_int = int(stat_id) if isinstance(stat_id, str) else stat_id

        if stat_id_int not in allowed_ids:
            continue

        # GP is always an integer
        if stat_id_int == 0:
            stats["GP"] = int(value) if value else 0
            continue

        # Determine type from config or fallback
        if stat_id_configs and stat_id_int in stat_id_configs:
            cfg = stat_id_configs[stat_id_int]
            name = cfg.key
            if cfg.is_percentage:
                stats[name] = float(value) if value else 0.0
            else:
                stats[name] = int(float(value)) if value else 0
        else:
            # Legacy fallback
            name = STAT_ID_MAP.get(stat_id_int)
            if name is None:
                continue
            if name in ("FG%", "FT%"):
                stats[name] = float(value) if value else 0.0
            else:
                stats[name] = int(float(value)) if value else 0

    return stats


def compute_roto_points(
    teams_data: list[dict],
    category_config: Optional[List[CategoryConfig]] = None,
) -> dict:
    """Compute per-category roto points for each team.

    In roto scoring, teams are ranked 1-N in each category.
    Best value gets N points, worst gets 1. Ties get averaged ranks.
    Respects category directionality (higher_is_better).

    Args:
        teams_data: List of dicts with "team_name" and "stats" keys.
        category_config: Optional dynamic category config. Falls back to
            ROTO_CATEGORIES (8-cat, all higher-is-better) when None.

    Returns:
        Dict mapping team_name → {category: roto_points}.
    """
    if category_config is not None:
        cats = [(c.key, c.higher_is_better) for c in category_config]
    else:
        cats = [(c, True) for c in ROTO_CATEGORIES]

    roto: dict[str, dict] = {t["team_name"]: {} for t in teams_data}

    for cat_key, higher_is_better in cats:
        # Collect (value, team_name) pairs, skip teams with missing data
        entries = []
        for t in teams_data:
            val = t["stats"].get(cat_key)
            if val is not None:
                entries.append((float(val), t["team_name"]))

        # Sort so that worst value comes first (rank 1) and best comes last (rank N).
        # For higher-is-better: ascending sort (lowest = worst).
        # For lower-is-better: descending sort (highest = worst).
        if higher_is_better:
            entries.sort(key=lambda x: (x[0], x[1]))
        else:
            entries.sort(key=lambda x: (-x[0], x[1]))

        # Assign ranks with tie averaging
        i = 0
        while i < len(entries):
            j = i
            while j < len(entries) and entries[j][0] == entries[i][0]:
                j += 1

            avg_rank = sum(range(i + 1, j + 1)) / (j - i)

            for k in range(i, j):
                team_name = entries[k][1]
                roto[team_name][cat_key] = avg_rank if avg_rank != int(avg_rank) else int(avg_rank)

            i = j

        # Teams with missing data get rank 1 (worst)
        for t in teams_data:
            if cat_key not in roto[t["team_name"]]:
                roto[t["team_name"]][cat_key] = 1

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
    _configure_session_retries(oauth.session)
    game = Game(oauth, "nba")
    game_id = game.game_id()

    full_league_id = f"{game_id}.l.{league_id}"
    logger.info(f"Fetching standings for league {full_league_id}...")

    league = game.to_league(full_league_id)

    # Get standings (rank, team name, total points)
    standings = league.standings()

    # ── Build dynamic category config from raw league settings ──
    raw_settings = league.yhandler.get_settings_raw(league.league_id)
    category_config = build_category_config_from_raw(raw_settings)

    if not category_config:
        # Fallback: use library's stat_categories() + legacy matching
        stat_cats = league.stat_categories()
        from fba.category_config import build_category_config_from_list
        category_config = build_category_config_from_list(
            [{"display_name": c["display_name"]} for c in stat_cats]
        )

    if not category_config:
        logger.warning("Could not determine league categories; using default 8-cat config")
        category_config = list(DEFAULT_8CAT_CONFIG)

    logger.info(
        f"League categories ({len(category_config)}): "
        f"{[c.key for c in category_config]}"
    )

    # Build stat_id filter for team stat ingestion
    stat_id_configs = build_stat_id_map(category_config)

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
        stats = _get_team_stats_raw(oauth.session, team_key, stat_id_configs)

        teams_data.append({
            "team_key": team_key,
            "team_name": team_name,
            "rank": rank,
            "total_points": total_points,
            "pts_change": pts_change,
            "stats": stats,
        })

    # Compute per-category roto points using dynamic config
    roto = compute_roto_points(teams_data, category_config)

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
        "league": {
            "categories": [{"display_name": c.display} for c in category_config],
            "category_config": to_serializable(category_config),
        },
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
