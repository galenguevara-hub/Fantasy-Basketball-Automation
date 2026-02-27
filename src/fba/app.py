#!/usr/bin/env python3
"""
Fantasy Basketball Standings Web App

Serves a dashboard that mirrors the Yahoo Fantasy standings page.
Use /refresh (POST) to trigger a fresh data pull via the Yahoo Fantasy API.
"""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

from fba.analysis.category_targets import compute_gaps_and_scores
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
_PROJECT_DIR = Path(__file__).parent.parent.parent
FRONTEND_DIST_DIR = _PROJECT_DIR / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
STANDINGS_FILE = _DATA_DIR / "standings.json"
CONFIG_FILE = _DATA_DIR / "config.json"
UI_MODE_ENV = "FBA_UI_MODE"
VALID_UI_MODES = {"auto", "react", "legacy"}


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


def _has_frontend_build() -> bool:
    """Return True when a React production build exists on disk."""
    return FRONTEND_INDEX_FILE.exists()


def _get_ui_mode() -> str:
    """Get configured UI mode, defaulting to react when invalid/unset."""
    mode = os.getenv(UI_MODE_ENV, "react").strip().lower()
    if mode not in VALID_UI_MODES:
        logger.warning(f"Invalid {UI_MODE_ENV}='{mode}' (expected auto|react|legacy). Falling back to react.")
        return "react"
    # Keep `auto` accepted for backwards compatibility, but treat it as strict React mode.
    if mode == "auto":
        return "react"
    return mode


def _is_legacy_ui_mode() -> bool:
    """Return True only when legacy template mode is explicitly requested."""
    return _get_ui_mode() == "legacy"


def _render_react_index():
    """Serve the built React app entrypoint."""
    return send_from_directory(FRONTEND_DIST_DIR, "index.html")


def _render_react_or_503():
    """Serve React index or return 503 when React mode is forced without a build."""
    if not _has_frontend_build():
        abort(503, description="React build not found. Run `npm --prefix frontend run build` or set FBA_UI_MODE=legacy.")
    return _render_react_index()


def _build_overview_payload(data: Optional[dict], league_id: str) -> dict[str, Any]:
    """Build standings overview payload for both templates and JSON API."""
    if data is None:
        return {
            "teams": [],
            "categories": [],
            "scraped_at": None,
            "per_game_rows": [],
            "ranking_rows": [],
            "league_id": league_id,
            "has_data": False,
        }

    teams = data.get("teams", [])
    categories = [cat["display_name"] for cat in data.get("league", {}).get("categories", [])]
    scraped_at = data.get("scraped_at")

    normalized = normalize_standings(teams)
    per_game_rows = normalized.get("per_game_rows", [])
    ranking_rows = normalized.get("ranking_rows", [])

    return {
        "teams": teams,
        "categories": categories,
        "scraped_at": scraped_at,
        "per_game_rows": per_game_rows,
        "ranking_rows": ranking_rows,
        "league_id": league_id,
        "has_data": True,
    }


def _build_analysis_payload(data: Optional[dict], league_id: str, selected_team: Optional[str]) -> dict[str, Any]:
    """Build category analysis payload for both templates and JSON API."""
    if data is None:
        return {
            "team_names": [],
            "selected_team": None,
            "analysis": [],
            "team_cluster": {},
            "team_pg_rank": {},
            "league_summary": [],
            "scraped_at": None,
            "league_id": league_id,
            "has_data": False,
        }

    teams = data.get("teams", [])
    scraped_at = data.get("scraped_at")

    normalized = normalize_standings(teams)
    per_game_rows = normalized.get("per_game_rows", [])
    ranking_rows = normalized.get("ranking_rows", [])
    team_names = [r["team_name"] for r in per_game_rows]

    valid_ranking = [r for r in ranking_rows if r.get("rank_total") is not None]
    valid_ranking.sort(key=lambda r: (-r["rank_total"], r["team_name"]))
    team_pg_rank = {r["team_name"]: _ordinal(i + 1) for i, r in enumerate(valid_ranking)}

    if selected_team not in team_names and team_names:
        selected_team = team_names[0]

    all_analysis = compute_gaps_and_scores(per_game_rows)
    team_analysis = all_analysis.get(selected_team, [])

    all_cluster = compute_cluster_metrics(per_game_rows)
    team_cluster = all_cluster.get(selected_team, {})

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

    return {
        "team_names": team_names,
        "selected_team": selected_team,
        "analysis": team_analysis,
        "team_cluster": team_cluster,
        "team_pg_rank": team_pg_rank,
        "league_summary": league_summary,
        "scraped_at": scraped_at,
        "league_id": league_id,
        "has_data": True,
    }


def _parse_games_played_inputs(args) -> dict[str, Any]:
    """Parse and validate games played query parameters."""
    start_str = args.get("start", _SEASON_START.isoformat())
    end_str = args.get("end", _SEASON_END.isoformat())
    date_error = None

    try:
        start_date = date.fromisoformat(start_str)
    except ValueError:
        start_date = _SEASON_START
        start_str = _SEASON_START.isoformat()
        date_error = f"Invalid start date '{args.get('start')}' — using default."

    try:
        end_date = date.fromisoformat(end_str)
    except ValueError:
        end_date = _SEASON_END
        end_str = _SEASON_END.isoformat()
        date_error = f"Invalid end date '{args.get('end')}' — using default."

    try:
        total_games = int(args.get("total_games", _DEFAULT_TOTAL_GAMES))
        if total_games <= 0:
            total_games = _DEFAULT_TOTAL_GAMES
    except (ValueError, TypeError):
        total_games = _DEFAULT_TOTAL_GAMES

    return {
        "start_str": start_str,
        "end_str": end_str,
        "start_date": start_date,
        "end_date": end_date,
        "total_games": total_games,
        "date_error": date_error,
    }


def _build_games_played_payload(
    data: Optional[dict],
    league_id: str,
    start_str: str,
    end_str: str,
    start_date: date,
    end_date: date,
    total_games: int,
    date_error: Optional[str],
) -> dict[str, Any]:
    """Build games-played payload for both templates and JSON API."""
    if data is None:
        return {
            "rows": [],
            "start_str": start_str,
            "end_str": end_str,
            "total_games": total_games,
            "elapsed_days": None,
            "remaining_days": None,
            "date_valid": False,
            "date_error": date_error,
            "scraped_at": None,
            "league_id": league_id,
            "has_data": False,
        }

    teams = data.get("teams", [])
    scraped_at = data.get("scraped_at")
    today = date.today()

    rows, date_valid = compute_games_played_metrics(teams, start_date, end_date, today, total_games=total_games)

    normalized = normalize_standings(teams)
    rank_total_by_team = {
        r["team_name"]: r.get("rank_total")
        for r in normalized.get("ranking_rows", [])
    }
    for row in rows:
        row["rank_total"] = rank_total_by_team.get(row["team_name"])

    rows.sort(key=lambda r: (r["rank"] if r["rank"] is not None else 999))

    elapsed_days = rows[0]["elapsed_days"] if rows else None
    remaining_days = rows[0]["remaining_days"] if rows else None

    if not date_valid and date_error is None:
        if today < start_date:
            date_error = f"Season hasn't started yet (starts {start_str})."
        elif today > end_date:
            date_error = f"Season has ended (ended {end_str})."

    return {
        "rows": rows,
        "start_str": start_str,
        "end_str": end_str,
        "total_games": total_games,
        "elapsed_days": elapsed_days,
        "remaining_days": remaining_days,
        "date_valid": date_valid,
        "date_error": date_error,
        "scraped_at": scraped_at,
        "league_id": league_id,
        "has_data": True,
    }


@app.route("/", methods=["GET"])
def index():
    """Render the standings dashboard."""
    if not _is_legacy_ui_mode():
        return _render_react_or_503()

    config = load_config()
    league_id = config.get("league_id", "")
    payload = _build_overview_payload(load_standings(), league_id)
    return render_template("index.html", **payload)


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
    if not _is_legacy_ui_mode():
        return _render_react_or_503()

    config = load_config()
    league_id = config.get("league_id", "")
    requested_team = request.args.get("team")
    payload = _build_analysis_payload(load_standings(), league_id, requested_team)
    return render_template("analysis.html", **payload)


_SEASON_START = date(2025, 10, 14)
_SEASON_END = date(2026, 3, 22)
_DEFAULT_TOTAL_GAMES = 816


@app.route("/games-played", methods=["GET"])
def games_played():
    """Render the games played pace analysis page."""
    if not _is_legacy_ui_mode():
        return _render_react_or_503()

    config = load_config()
    league_id = config.get("league_id", "")
    params = _parse_games_played_inputs(request.args)
    payload = _build_games_played_payload(load_standings(), league_id, **params)
    return render_template("games_played.html", **payload)


@app.route("/api/config", methods=["GET"])
def api_config():
    """Return current config (league ID, auth status)."""
    config = load_config()
    return jsonify({
        "league_id": config.get("league_id", ""),
        "has_session": is_authenticated(),
    })


@app.route("/api/overview", methods=["GET"])
def api_overview():
    """Return standings overview payload for React clients."""
    config = load_config()
    league_id = config.get("league_id", "")
    payload = _build_overview_payload(load_standings(), league_id)
    return jsonify(payload)


@app.route("/api/analysis", methods=["GET"])
def api_analysis():
    """Return target-category analysis payload for React clients."""
    config = load_config()
    league_id = config.get("league_id", "")
    payload = _build_analysis_payload(load_standings(), league_id, request.args.get("team"))
    return jsonify(payload)


@app.route("/api/games-played", methods=["GET"])
def api_games_played():
    """Return games played analysis payload for React clients."""
    config = load_config()
    league_id = config.get("league_id", "")
    params = _parse_games_played_inputs(request.args)
    payload = _build_games_played_payload(load_standings(), league_id, **params)
    return jsonify(payload)


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


@app.route("/assets/<path:filename>", methods=["GET"])
def frontend_assets(filename: str):
    """Serve React build asset files."""
    if not _has_frontend_build():
        abort(404)

    assets_dir = FRONTEND_DIST_DIR / "assets"
    if not assets_dir.exists():
        abort(404)

    return send_from_directory(assets_dir, filename)


if __name__ == "__main__":
    port = 8080
    logger.info("=" * 60)
    logger.info("Fantasy Basketball Standings App")
    logger.info("=" * 60)
    logger.info(f"Open: http://localhost:{port}")
    logger.info(f"API:  http://localhost:{port}/api/standings")
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
