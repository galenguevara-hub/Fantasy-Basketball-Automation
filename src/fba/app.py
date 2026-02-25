#!/usr/bin/env python3
"""
Fantasy Basketball Standings Web App

Serves a dashboard that mirrors the Yahoo Fantasy standings page.
Use /refresh (POST) to trigger a fresh data pull via the Yahoo Fantasy API.
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from fba.analysis.category_targets import CATEGORIES, compute_gaps_and_scores
from fba.analysis.cluster_leverage import compute_cluster_metrics
from fba.analysis.games_played import compute_games_played_metrics
from fba.normalize import normalize_standings
from fba.yahoo_api import (
    AuthError,
    YahooAPIError,
    fetch_and_save,
    is_authenticated,
    OAUTH_FILE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
STANDINGS_FILE = _DATA_DIR / "standings.json"
CONFIG_FILE = _DATA_DIR / "config.json"


def load_config() -> dict:
    """Load app config from disk."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict):
    """Save app config to disk."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_standings() -> "dict | None":
    """Load standings data from disk, returning None if unavailable."""
    if not STANDINGS_FILE.exists():
        return None
    try:
        with open(STANDINGS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to read standings.json: {e}")
        return None


@app.route("/", methods=["GET"])
def index():
    """Render the standings dashboard."""
    config = load_config()
    league_id = config.get("league_id", "")
    data = load_standings()

    if data is None:
        return render_template(
            "index.html",
            teams=[],
            categories=[],
            scraped_at=None,
            per_game_rows=[],
            ranking_rows=[],
            league_id=league_id,
        )

    teams = data.get("teams", [])
    categories = [cat["display_name"] for cat in data.get("league", {}).get("categories", [])]
    scraped_at = data.get("scraped_at")

    # Normalize standings for per-game analysis
    normalized = normalize_standings(teams)
    per_game_rows = normalized.get("per_game_rows", [])
    ranking_rows = normalized.get("ranking_rows", [])

    return render_template(
        "index.html",
        teams=teams,
        categories=categories,
        scraped_at=scraped_at,
        per_game_rows=per_game_rows,
        ranking_rows=ranking_rows,
        league_id=league_id,
    )


def _ordinal(n: int) -> str:
    """Convert an integer to its ordinal string (1st, 2nd, 3rd, ...)."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


@app.route("/analysis", methods=["GET"])
def analysis():
    """Render the category targets analysis page."""
    config = load_config()
    league_id = config.get("league_id", "")
    data = load_standings()

    if data is None:
        return render_template(
            "analysis.html",
            team_names=[],
            selected_team=None,
            analysis=None,
            team_pg_rank={},
            scraped_at=None,
            league_id=league_id,
        )

    teams = data.get("teams", [])
    scraped_at = data.get("scraped_at")

    # Build per-game rows and ranking rows.
    normalized = normalize_standings(teams)
    per_game_rows = normalized.get("per_game_rows", [])
    ranking_rows = normalized.get("ranking_rows", [])

    team_names = [r["team_name"] for r in per_game_rows]

    # Build per-game total rank: sort by rank_total descending (higher = better).
    # Maps team_name → ordinal string e.g. "1st", "3rd".
    valid_ranking = [r for r in ranking_rows if r.get("rank_total") is not None]
    valid_ranking.sort(key=lambda r: (-r["rank_total"], r["team_name"]))
    team_pg_rank = {r["team_name"]: _ordinal(i + 1) for i, r in enumerate(valid_ranking)}

    # Determine which team to show.
    selected_team = request.args.get("team", team_names[0] if team_names else None)
    if selected_team not in team_names and team_names:
        selected_team = team_names[0]

    # Compute Layer 1 analysis for all teams.
    all_analysis = compute_gaps_and_scores(per_game_rows)
    team_analysis = all_analysis.get(selected_team, [])

    # Compute Layer 2 cluster leverage for the selected team.
    all_cluster = compute_cluster_metrics(per_game_rows)
    team_cluster = all_cluster.get(selected_team, {})

    # Build league-wide summary ordered by per-game rank total (best first).
    league_summary = []
    for row in sorted(valid_ranking, key=lambda r: (-r["rank_total"], r["team_name"])):
        name = row["team_name"]
        cats = all_analysis.get(name, [])
        targets = sorted(
            [c for c in cats if c["tag"] == "TARGET"],
            key=lambda c: -(c["target_score"] or 0),
        )
        defends = sorted(
            [c for c in cats if c["tag"] == "DEFEND"],
            key=lambda c: -(c["target_score"] or 0),
        )

        # Cluster TARGET/DEFEND categories for this team (Layer 2).
        cluster_cats = all_cluster.get(name, {})
        cluster_targets = sorted(
            [cn for cn, m in cluster_cats.items() if m.get("tag") == "TARGET"],
            key=lambda cn: -(cluster_cats[cn].get("cluster_up_score") or 0),
        )
        cluster_defends = sorted(
            [cn for cn, m in cluster_cats.items() if m.get("tag") == "DEFEND"],
            key=lambda cn: -(cluster_cats[cn].get("cluster_down_risk") or 0),
        )

        league_summary.append({
            "team_name": name,
            "rank_total": row["rank_total"],
            "total_points": row.get("total_points"),
            "pg_rank": team_pg_rank.get(name, "—"),
            "targets": targets,
            "defends": defends,
            "cluster_targets": cluster_targets,
            "cluster_defends": cluster_defends,
        })

    return render_template(
        "analysis.html",
        team_names=team_names,
        selected_team=selected_team,
        analysis=team_analysis,
        team_cluster=team_cluster,
        team_pg_rank=team_pg_rank,
        league_summary=league_summary,
        scraped_at=scraped_at,
        league_id=league_id,
    )


_SEASON_START = date(2025, 10, 14)
_SEASON_END = date(2026, 3, 22)
_DEFAULT_TOTAL_GAMES = 816


@app.route("/games-played", methods=["GET"])
def games_played():
    """Render the games played pace analysis page."""
    config = load_config()
    league_id = config.get("league_id", "")
    data = load_standings()

    if data is None:
        return render_template(
            "games_played.html",
            rows=[],
            start_str=_SEASON_START.isoformat(),
            end_str=_SEASON_END.isoformat(),
            total_games=_DEFAULT_TOTAL_GAMES,
            elapsed_days=None,
            remaining_days=None,
            date_valid=False,
            date_error=None,
            scraped_at=None,
            league_id=league_id,
        )

    teams = data.get("teams", [])
    scraped_at = data.get("scraped_at")

    # Parse user-supplied dates (fall back to season defaults on bad input)
    start_str = request.args.get("start", _SEASON_START.isoformat())
    end_str = request.args.get("end", _SEASON_END.isoformat())
    date_error = None

    try:
        start_date = date.fromisoformat(start_str)
    except ValueError:
        start_date = _SEASON_START
        start_str = _SEASON_START.isoformat()
        date_error = f"Invalid start date '{request.args.get('start')}' — using default."

    try:
        end_date = date.fromisoformat(end_str)
    except ValueError:
        end_date = _SEASON_END
        end_str = _SEASON_END.isoformat()
        date_error = f"Invalid end date '{request.args.get('end')}' — using default."

    try:
        total_games = int(request.args.get("total_games", _DEFAULT_TOTAL_GAMES))
        if total_games <= 0:
            total_games = _DEFAULT_TOTAL_GAMES
    except (ValueError, TypeError):
        total_games = _DEFAULT_TOTAL_GAMES

    today = date.today()

    rows, date_valid = compute_games_played_metrics(teams, start_date, end_date, today, total_games=total_games)

    # Attach per-game rank total to each row
    normalized = normalize_standings(teams)
    rank_total_by_team = {
        r["team_name"]: r.get("rank_total")
        for r in normalized.get("ranking_rows", [])
    }
    for row in rows:
        row["rank_total"] = rank_total_by_team.get(row["team_name"])

    # Preserve roto standings order (rank from Yahoo data)
    rows.sort(key=lambda r: (r["rank"] if r["rank"] is not None else 999))

    elapsed_days = rows[0]["elapsed_days"] if rows else None
    remaining_days = rows[0]["remaining_days"] if rows else None

    if not date_valid and date_error is None:
        if today < start_date:
            date_error = f"Season hasn't started yet (starts {start_str})."
        elif today > end_date:
            date_error = f"Season has ended (ended {end_str})."

    return render_template(
        "games_played.html",
        rows=rows,
        start_str=start_str,
        end_str=end_str,
        total_games=total_games,
        elapsed_days=elapsed_days,
        remaining_days=remaining_days,
        date_valid=date_valid,
        date_error=date_error,
        scraped_at=scraped_at,
        league_id=league_id,
    )


@app.route("/api/config", methods=["GET"])
def api_config():
    """Return current config (league ID, auth status)."""
    config = load_config()
    return jsonify({
        "league_id": config.get("league_id", ""),
        "has_session": is_authenticated(),
    })


@app.route("/api/config", methods=["POST"])
def set_config():
    """Save league ID to config."""
    data = request.get_json()
    league_id = data.get("league_id", "").strip()

    if not league_id:
        return jsonify({"status": "error", "error": "League ID is required."}), 400

    if not league_id.isdigit():
        return jsonify({"status": "error", "error": "League ID must be a number."}), 400

    config = load_config()
    config["league_id"] = league_id
    save_config(config)

    logger.info(f"League ID set to {league_id}")
    return jsonify({"status": "success", "league_id": league_id})


@app.route("/refresh", methods=["POST"])
def refresh():
    """Fetch fresh standings from the Yahoo Fantasy API."""
    config = load_config()
    league_id = config.get("league_id", "")

    if not league_id:
        return jsonify({"status": "error", "error": "No league ID configured."}), 400

    if not OAUTH_FILE.exists():
        return jsonify({
            "status": "error",
            "error": "Yahoo API not authorized. Run: python -m fba.oauth_setup",
        }), 401

    logger.info(f"Refresh requested — fetching standings via Yahoo API for league {league_id}...")

    try:
        data = fetch_and_save(league_id)
        teams_count = len(data.get("teams", []))

        logger.info(f"API fetch complete — {teams_count} teams updated.")
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
            "teams_updated": teams_count,
        })

    except AuthError as e:
        logger.error(f"Auth error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "session_expired": True,
        }), 401

    except YahooAPIError as e:
        logger.error(f"Yahoo API error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

    except Exception as e:
        logger.error(f"Unexpected error during refresh: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/standings", methods=["GET"])
def api_standings():
    """Return the raw standings JSON."""
    data = load_standings()
    if data is None:
        return jsonify({"error": "No standings data available. Run a refresh first."}), 404
    return jsonify(data)


if __name__ == "__main__":
    port = 8080
    logger.info("=" * 60)
    logger.info("Fantasy Basketball Standings App")
    logger.info("=" * 60)
    logger.info(f"Open: http://localhost:{port}")
    logger.info(f"API:  http://localhost:{port}/api/standings")
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
