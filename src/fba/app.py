#!/usr/bin/env python3
"""
Fantasy Basketball Standings Web App

Serves a dashboard that mirrors the Yahoo Fantasy standings page.
Use /refresh (POST) to trigger a fresh data pull via the Yahoo Fantasy API.
"""

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
load_dotenv(override=True)

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, session
from flask_login import current_user, login_required
from flask_session import Session
from redis import Redis

from fba.analysis.category_targets import compute_gaps_and_scores
from fba.analysis.cluster_leverage import compute_cluster_metrics
from fba.analysis.games_played import compute_games_played_metrics
from fba.auth import (
    build_auth_url,
    clear_user_session,
    exchange_code_for_tokens,
    fetch_yahoo_user_info,
    get_valid_tokens,
    login_manager,
    store_user_session,
)
from fba.config import Config
from fba.normalize import normalize_standings
from fba.yahoo_api import (
    AuthError,
    YahooAPIError,
    fetch_standings,
    get_oauth_session_from_tokens,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Redis-backed sessions (only when REDIS_URL is configured)
_redis_client: "Redis | None" = None
if Config.REDIS_URL:
    _redis_client = Redis.from_url(Config.REDIS_URL)
    app.config["SESSION_TYPE"] = "redis"
    app.config["SESSION_REDIS"] = _redis_client
    app.config["SESSION_KEY_PREFIX"] = "fba:session:"
    app.config["SESSION_PERMANENT"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    app.config["SESSION_SERIALIZATION_FORMAT"] = "json"
    Session(app)

# Initialize Flask-Login (return 401 JSON for unauthorized API requests)
login_manager.init_app(app)


@login_manager.unauthorized_handler
def unauthorized():
    """Return 401 JSON instead of redirect for API requests."""
    return jsonify({"error": "Authentication required", "authenticated": False}), 401

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_PROJECT_DIR = Path(__file__).parent.parent.parent
FRONTEND_DIST_DIR = _PROJECT_DIR / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
STANDINGS_FILE = _DATA_DIR / "standings.json"
CONFIG_FILE = _DATA_DIR / "config.json"
UI_MODE_ENV = "FBA_UI_MODE"
VALID_UI_MODES = {"auto", "react", "legacy"}

# ---------------------------------------------------------------------------
# Redis-backed standings cache (per-user, keyed by user_id + league_id)
# ---------------------------------------------------------------------------
_STANDINGS_TTL = 3600  # 1 hour


def _cache_get(user_id: str, league_id: str) -> "dict | None":
    """Retrieve standings from Redis for this user+league. Returns None on miss or no Redis."""
    if _redis_client is None or not league_id:
        return None
    try:
        raw = _redis_client.get(f"fba:standings:{user_id}:{league_id}")
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Redis cache read failed: %s", exc)
        return None


def _cache_set(user_id: str, league_id: str, data: dict) -> None:
    """Write standings to Redis with TTL. Silently skips when Redis is unavailable."""
    if _redis_client is None:
        return
    try:
        _redis_client.setex(f"fba:standings:{user_id}:{league_id}", _STANDINGS_TTL, json.dumps(data))
    except Exception as exc:
        logger.warning("Redis cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Per-user refresh rate limiting
# ---------------------------------------------------------------------------
_REFRESH_COOLDOWN = 30  # seconds


def _check_refresh_rate_limit(user_id: str) -> bool:
    """Return True if the user is allowed to refresh (not in cooldown).

    Sets a Redis key with TTL on first call; subsequent calls within the window
    return False. Always returns True when Redis is unavailable.
    """
    if _redis_client is None:
        return True
    try:
        key = f"fba:refresh_cooldown:{user_id}"
        return bool(_redis_client.set(key, "1", ex=_REFRESH_COOLDOWN, nx=True))
    except Exception as exc:
        logger.warning("Redis rate-limit check failed: %s", exc)
        return True  # fail open


# ---------------------------------------------------------------------------
# League ID long-term persistence (survives session expiry)
# ---------------------------------------------------------------------------
_LEAGUE_ID_TTL = 365 * 24 * 3600  # 1 year


def _persist_league_id(user_id: str, league_id: str) -> None:
    """Store a user's league ID in Redis long-term, keyed by user_id."""
    if _redis_client is None:
        return
    try:
        _redis_client.setex(f"fba:league_id:{user_id}", _LEAGUE_ID_TTL, league_id)
    except Exception as exc:
        logger.warning("Redis league_id persist failed: %s", exc)


def _restore_league_id(user_id: str) -> str:
    """Retrieve a user's persisted league ID from Redis. Returns '' on miss."""
    if _redis_client is None:
        return ""
    try:
        raw = _redis_client.get(f"fba:league_id:{user_id}")
        return raw.decode() if raw else ""
    except Exception as exc:
        logger.warning("Redis league_id restore failed: %s", exc)
        return ""


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


def _get_standings(league_id: str) -> "dict | None":
    """Return standings for the current user+league, checking Redis cache first.

    Cache key is scoped per user_id so different users with the same league_id
    see only their own cached data. Falls back to disk only in legacy UI mode.
    """
    if league_id and current_user.is_authenticated:
        cached = _cache_get(current_user.id, league_id)
        if cached is not None:
            return cached
    if _is_legacy_ui_mode():
        return load_standings()
    return None


def _get_league_id() -> str:
    """Return the league ID for the current user from their session.

    Falls back to the shared config file only in legacy UI mode.
    """
    league_id = session.get("league_id", "")
    if league_id:
        return league_id
    if _is_legacy_ui_mode():
        config = load_config()
        return config.get("league_id", "")
    return ""


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


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/auth/yahoo")
def auth_yahoo():
    """Redirect the user to Yahoo for OAuth authorization."""
    if not Config.YAHOO_CLIENT_ID:
        return jsonify({"error": "YAHOO_CLIENT_ID not configured"}), 500
    url = build_auth_url()
    logger.info("Redirecting user to Yahoo OAuth: %s", url)
    return redirect(url)


@app.route("/debug/auth-url")
def debug_auth_url():
    """Show the exact OAuth authorization URL for debugging (dev only)."""
    url = build_auth_url()
    return jsonify({
        "auth_url": url,
        "client_id": Config.YAHOO_CLIENT_ID,
        "redirect_uri": Config.YAHOO_REDIRECT_URI,
        "redirect_uri_env": os.environ.get("YAHOO_REDIRECT_URI", "(not set)"),
    })


@app.route("/auth/yahoo/callback")
def auth_yahoo_callback():
    """Handle the OAuth callback from Yahoo."""
    error = request.args.get("error")
    if error:
        logger.warning("Yahoo OAuth error: %s", error)
        return redirect("/?auth_error=" + error)

    code = request.args.get("code")
    if not code:
        return redirect("/?auth_error=no_code")

    tokens = exchange_code_for_tokens(code)
    if not tokens:
        return redirect("/?auth_error=token_exchange_failed")

    yahoo_guid, display_name = fetch_yahoo_user_info(tokens["access_token"])
    store_user_session(yahoo_guid, display_name, tokens)

    if not session.get("league_id"):
        stored = _restore_league_id(yahoo_guid)
        if stored:
            session["league_id"] = stored
            session.modified = True

    logger.info("User %s (%s) logged in via Yahoo OAuth.", display_name, yahoo_guid)
    return redirect("/")


@app.route("/auth/code", methods=["POST"])
def auth_manual_code():
    """Accept a manually-entered authorization code (OOB fallback).

    If Yahoo shows the authorization code on-screen instead of redirecting,
    users can paste it here to complete login.
    """
    data = request.get_json()
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"error": "Authorization code is required."}), 400

    tokens = exchange_code_for_tokens(code)
    if not tokens:
        return jsonify({"error": "Failed to exchange code for tokens. The code may have expired."}), 400

    yahoo_guid, display_name = fetch_yahoo_user_info(tokens["access_token"])
    store_user_session(yahoo_guid, display_name, tokens)

    if not session.get("league_id"):
        stored = _restore_league_id(yahoo_guid)
        if stored:
            session["league_id"] = stored
            session.modified = True

    logger.info("User %s (%s) logged in via manual code entry.", display_name, yahoo_guid)
    return jsonify({"status": "success", "user_name": display_name})


@app.route("/logout", methods=["POST"])
def logout():
    """Clear the user session."""
    clear_user_session()
    return jsonify({"status": "success"})


@app.route("/api/auth/status")
def auth_status():
    """Return current authentication state."""
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "user_name": current_user.display_name,
        })
    return jsonify({"authenticated": False})


# ---------------------------------------------------------------------------
# Config + data API routes
# ---------------------------------------------------------------------------

@app.route("/api/config", methods=["GET"])
def api_config():
    """Return current config (league ID, auth status)."""
    return jsonify({
        "league_id": _get_league_id(),
        "has_session": current_user.is_authenticated,
    })


@app.route("/api/overview", methods=["GET"])
def api_overview():
    """Return standings overview payload for React clients."""
    league_id = _get_league_id()
    payload = _build_overview_payload(_get_standings(league_id), league_id)
    return jsonify(payload)


@app.route("/api/analysis", methods=["GET"])
def api_analysis():
    """Return target-category analysis payload for React clients."""
    league_id = _get_league_id()
    payload = _build_analysis_payload(_get_standings(league_id), league_id, request.args.get("team"))
    return jsonify(payload)


@app.route("/api/games-played", methods=["GET"])
def api_games_played():
    """Return games played analysis payload for React clients."""
    league_id = _get_league_id()
    params = _parse_games_played_inputs(request.args)
    payload = _build_games_played_payload(_get_standings(league_id), league_id, **params)
    return jsonify(payload)


@app.route("/api/config", methods=["POST"])
def set_config():
    """Save league ID to the session (no auth required)."""
    data = request.get_json()
    league_id = data.get("league_id", "").strip()

    if not league_id:
        return jsonify({"status": "error", "error": "League ID is required."}), 400

    if not league_id.isdigit():
        return jsonify({"status": "error", "error": "League ID must be a number."}), 400

    session["league_id"] = league_id
    session.modified = True

    if current_user.is_authenticated:
        _persist_league_id(current_user.id, league_id)

    user_name = current_user.display_name if current_user.is_authenticated else "anonymous"
    logger.info("User %s set league ID to %s", user_name, league_id)
    return jsonify({"status": "success", "league_id": league_id})


@app.route("/refresh", methods=["POST"])
@login_required
def refresh():
    """Fetch fresh standings from the Yahoo Fantasy API using session tokens."""
    league_id = _get_league_id()

    if not league_id:
        return jsonify({"status": "error", "error": "No league ID configured."}), 400

    if not _check_refresh_rate_limit(current_user.id):
        return jsonify({"status": "error", "error": "Please wait before refreshing again."}), 429

    tokens = get_valid_tokens()
    if not tokens:
        clear_user_session()
        return jsonify({
            "status": "error",
            "error": "Not authenticated. Please log in with Yahoo.",
            "session_expired": True,
        }), 401

    logger.info(
        "Refresh requested by %s — fetching standings for league %s...",
        current_user.display_name,
        league_id,
    )

    try:
        oauth = get_oauth_session_from_tokens(tokens["access_token"], tokens["refresh_token"])
        data = fetch_standings(league_id, oauth=oauth)

        # Store in Redis cache, scoped to this user+league
        _cache_set(current_user.id, league_id, data)
        teams_count = len(data.get("teams", []))

        logger.info("API fetch complete — %d teams updated.", teams_count)
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
            "teams_updated": teams_count,
        })

    except AuthError as e:
        logger.error("Auth error: %s", e)
        clear_user_session()
        return jsonify({
            "status": "error",
            "error": str(e),
            "session_expired": True,
        }), 401

    except YahooAPIError as e:
        logger.error("Yahoo API error: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500

    except Exception as e:
        logger.error("Unexpected error during refresh: %s", e)
        return jsonify({"status": "error", "error": str(e)}), 500


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
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
