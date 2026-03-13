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

from urllib.parse import quote

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, session
from flask_login import current_user, login_required
from flask_session import Session
from redis import Redis

from fba.analysis.category_targets import compute_gap_chart_data, compute_gaps_and_scores
from fba.analysis.cluster_leverage import compute_cluster_metrics
from fba.analysis.games_played import (
    COUNTING_CATEGORIES,
    compute_games_played_metrics,
    compute_projected_roto_ranks,
    compute_projected_totals,
)
from fba.analysis.executive_summary import build_executive_summary
from fba.auth import (
    build_auth_url,
    clear_user_session,
    exchange_code_for_tokens,
    fetch_yahoo_user_info,
    get_valid_tokens,
    login_manager,
    store_user_session,
    validate_oauth_state,
)
from fba.category_config import (
    CategoryConfig,
    from_serializable,
    get_counting_configs,
    to_serializable,
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

# Secure session cookie flags
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Only send cookies over HTTPS in production (Fly.io enforces HTTPS; skip for local dev)
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("FLY_APP_NAME"))

# Redis-backed sessions (only when REDIS_URL is configured)
_redis_client: "Redis | None" = None
if Config.REDIS_URL:
    _redis_client = Redis.from_url(Config.REDIS_URL)
    app.config["SESSION_TYPE"] = "redis"
    app.config["SESSION_REDIS"] = _redis_client
    app.config["SESSION_KEY_PREFIX"] = "fba:session:"
    app.config["SESSION_PERMANENT"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    app.config["SESSION_SERIALIZATION_FORMAT"] = "json"
    Session(app)

# Initialize Flask-Login (return 401 JSON for unauthorized API requests)
login_manager.init_app(app)

# Initialize time series SQLite database
from fba.timeseries.db import init_db as _init_timeseries_db
_init_timeseries_db()


@app.after_request
def set_security_headers(response):
    """Apply standard security headers to every response."""
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # CSP: allow same-origin scripts/styles plus inline (React build inlines chunks)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    return response


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
    """Write standings to Redis with TTL. Falls back to disk when Redis is unavailable."""
    if _redis_client is not None:
        try:
            _redis_client.setex(f"fba:standings:{user_id}:{league_id}", _STANDINGS_TTL, json.dumps(data))
            return
        except Exception as exc:
            logger.warning("Redis cache write failed: %s", exc)
    # Fallback: write to disk so _get_standings can find it without Redis
    try:
        with open(STANDINGS_FILE, "w") as f:
            json.dump(data, f)
    except OSError as exc:
        logger.warning("Disk standings write failed: %s", exc)


# ---------------------------------------------------------------------------
# Per-user refresh rate limiting
# ---------------------------------------------------------------------------
_REFRESH_COOLDOWN = 30  # seconds


def _check_refresh_rate_limit(user_id: str) -> int:
    """Return 0 if the user may refresh now, or remaining cooldown seconds if rate-limited.

    Sets a Redis key with TTL on first call; returns its remaining TTL on
    subsequent calls within the window. Returns 0 when Redis is unavailable
    (fail open).
    """
    if _redis_client is None:
        return 0
    try:
        key = f"fba:refresh_cooldown:{user_id}"
        allowed = _redis_client.set(key, "1", ex=_REFRESH_COOLDOWN, nx=True)
        if allowed:
            return 0
        ttl = _redis_client.ttl(key)
        return max(int(ttl), 1)
    except Exception as exc:
        logger.warning("Redis rate-limit check failed: %s", exc)
        return 0  # fail open


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
    # Fall back to disk (always, not just legacy mode — needed when Redis is unavailable)
    return load_standings()


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


def _extract_category_config(data: Optional[dict]) -> Optional[list[CategoryConfig]]:
    """Extract dynamic category config from standings data.

    Returns None for old-format data (graceful fallback to defaults).
    """
    if data is None:
        return None
    league = data.get("league", {})
    raw_config = league.get("category_config")
    if raw_config:
        try:
            return from_serializable(raw_config)
        except Exception:
            pass
    # Try legacy categories list
    legacy_cats = league.get("categories")
    if legacy_cats:
        try:
            return from_serializable(legacy_cats)
        except Exception:
            pass
    return None


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
    cat_config = _extract_category_config(data)
    categories = [cat["display_name"] for cat in data.get("league", {}).get("categories", [])]
    scraped_at = data.get("scraped_at")

    normalized = normalize_standings(teams, cat_config)
    per_game_rows = normalized.get("per_game_rows", [])
    ranking_rows = normalized.get("ranking_rows", [])

    payload: dict[str, Any] = {
        "teams": teams,
        "categories": categories,
        "scraped_at": scraped_at,
        "per_game_rows": per_game_rows,
        "ranking_rows": ranking_rows,
        "league_id": league_id,
        "has_data": True,
    }
    if cat_config:
        payload["category_config"] = to_serializable(cat_config)
    return payload


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
            "gap_chart": [],
            "scraped_at": None,
            "league_id": league_id,
            "has_data": False,
        }

    teams = data.get("teams", [])
    cat_config = _extract_category_config(data)
    scraped_at = data.get("scraped_at")

    normalized = normalize_standings(teams, cat_config)
    per_game_rows = normalized.get("per_game_rows", [])
    ranking_rows = normalized.get("ranking_rows", [])
    team_names = [r["team_name"] for r in per_game_rows]

    valid_ranking = [r for r in ranking_rows if r.get("rank_total") is not None]
    valid_ranking.sort(key=lambda r: (-r["rank_total"], r["team_name"]))
    team_pg_rank = {r["team_name"]: _ordinal(i + 1) for i, r in enumerate(valid_ranking)}

    if selected_team not in team_names and team_names:
        selected_team = team_names[0]

    all_analysis = compute_gaps_and_scores(per_game_rows, cat_config)
    team_analysis = all_analysis.get(selected_team, [])

    all_cluster = compute_cluster_metrics(per_game_rows, category_config=cat_config)
    team_cluster = all_cluster.get(selected_team, {})

    league_summary = []
    for row in sorted(valid_ranking, key=lambda r: (-r["rank_total"], r["team_name"])):
        name = row["team_name"]
        cats = all_analysis.get(name, [])
        targets = sorted(
            [c for c in cats if c.get("is_target")],
            key=lambda c: -(c["target_score"] or 0),
        )
        defends = sorted(
            [c for c in cats if c.get("is_defend")],
            key=lambda c: (c["z_gap_down"] if c["z_gap_down"] is not None else float("inf")),
        )

        cluster_cats = all_cluster.get(name, {})
        cluster_targets = sorted(
            [cn for cn, m in cluster_cats.items() if m.get("is_target")],
            key=lambda cn: -(cluster_cats[cn].get("cluster_up_score") or 0),
        )
        cluster_defends = sorted(
            [cn for cn, m in cluster_cats.items() if m.get("is_defend")],
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

    # Gap chart data for the selected team
    gap_chart = compute_gap_chart_data(per_game_rows, selected_team, cat_config) if selected_team else []

    return {
        "team_names": team_names,
        "selected_team": selected_team,
        "analysis": team_analysis,
        "team_cluster": team_cluster,
        "team_pg_rank": team_pg_rank,
        "league_summary": league_summary,
        "gap_chart": gap_chart,
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
    cat_config = _extract_category_config(data)
    scraped_at = data.get("scraped_at")
    today = date.today()

    rows, date_valid = compute_games_played_metrics(teams, start_date, end_date, today, total_games=total_games)

    normalized = normalize_standings(teams, cat_config)
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

    # Projected end-of-season counting totals and roto rankings
    projected_totals = compute_projected_totals(
        teams, start_date, end_date, today, total_games=total_games,
        category_config=cat_config,
    )
    projected_ranks = compute_projected_roto_ranks(projected_totals, teams, cat_config)

    # Sort projections by rank for consistent ordering
    projected_totals.sort(key=lambda r: (r["rank"] if r["rank"] is not None else 999))
    projected_ranks.sort(key=lambda r: (
        -(r["projected_total"] or 0),  # highest projected total first
        r.get("rank") or 999,
    ))

    # Category display metadata for the frontend
    if cat_config:
        counting_configs = get_counting_configs(cat_config)
        counting_cat_meta = [{"key": c.key, "display": c.display} for c in counting_configs]
    else:
        counting_cat_meta = [{"key": c["key"], "display": c["display"]} for c in COUNTING_CATEGORIES]

    return {
        "rows": rows,
        "projected_totals": projected_totals,
        "projected_ranks": projected_ranks,
        "counting_categories": counting_cat_meta,
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


def _build_executive_summary_payload(
    data: Optional[dict],
    league_id: str,
    selected_team: Optional[str],
    start_str: str,
    end_str: str,
    start_date: date,
    end_date: date,
    total_games: int,
    date_error: Optional[str],
) -> dict[str, Any]:
    """Build executive-summary payload for React clients."""
    if data is None:
        return {
            "team_names": [],
            "selected_team": None,
            "summary_card": {},
            "per_game_vs_raw_rows": [],
            "per_game_vs_raw_label": None,
            "category_opportunities": [],
            "best_categories_to_target": [],
            "categories_at_risk": [],
            "multi_point_swings": [],
            "games_pace": {},
            "nearby_teams": [],
            "nearby_team_insights": [],
            "projected_standings": [],
            "projected_finish": None,
            "category_competition": [],
            "category_stability": [],
            "high_leverage_categories": [],
            "actionable_insights": [],
            "trade_hints": [],
            "momentum": {
                "available": False,
                "message": "Historical snapshots are not available in the current dataset.",
            },
            "start_str": start_str,
            "end_str": end_str,
            "total_games": total_games,
            "date_error": date_error,
            "scraped_at": None,
            "league_id": league_id,
            "has_data": False,
        }

    teams = data.get("teams", [])
    cat_config = _extract_category_config(data)
    scraped_at = data.get("scraped_at")
    today = date.today()

    summary = build_executive_summary(
        teams=teams,
        selected_team=selected_team,
        start_date=start_date,
        end_date=end_date,
        today_date=today,
        total_games=total_games,
        category_config=cat_config,
    )

    return {
        **summary,
        "start_str": start_str,
        "end_str": end_str,
        "total_games": total_games,
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


@app.route("/executive-summary", methods=["GET"])
def executive_summary():
    """Render the executive summary page."""
    if not _is_legacy_ui_mode():
        return _render_react_or_503()

    # Legacy template mode has no dedicated executive page.
    return redirect("/analysis")


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/auth/yahoo")
def auth_yahoo():
    """Redirect the user to Yahoo for OAuth authorization."""
    if not Config.YAHOO_CLIENT_ID:
        return jsonify({"error": "YAHOO_CLIENT_ID not configured"}), 500
    url = build_auth_url()
    logger.info("Redirecting user to Yahoo OAuth authorization.")
    return redirect(url)



@app.route("/auth/yahoo/callback")
def auth_yahoo_callback():
    """Handle the OAuth callback from Yahoo.

    Also serves as the production relay for local-dev OAuth: when the state
    parameter begins with ``local_dev:<port>:``, the request is bounced to
    ``http://localhost:<port>/auth/yahoo/callback`` with the bare state token.
    This lets local dev use the stable production redirect URI so Yahoo only
    ever needs one registered callback URL — no tunnel URLs required.
    """
    error = request.args.get("error")
    if error:
        logger.warning("Yahoo OAuth error: %s", error)
        return redirect("/?auth_error=" + quote(error, safe=""))

    received_state = request.args.get("state", "")

    # Local-dev relay: bounce back to localhost if state has the local_dev prefix.
    if received_state.startswith("local_dev:"):
        parts = received_state.split(":", 2)
        if len(parts) == 3:
            _, local_port, bare_state = parts
            code = request.args.get("code", "")
            from urllib.parse import urlencode as _urlencode
            qs = _urlencode({"code": code, "state": bare_state})
            local_url = f"http://localhost:{local_port}/auth/yahoo/callback?{qs}"
            logger.info("Local-dev OAuth relay: bouncing to %s", local_url)
            return redirect(local_url)
        # Malformed local_dev state — fall through to normal rejection
        logger.warning("Malformed local_dev state: %s", received_state)
        return redirect("/?auth_error=state_mismatch")

    # Validate OAuth state parameter to prevent CSRF
    if not validate_oauth_state(received_state):
        logger.warning("OAuth callback rejected: state mismatch (possible CSRF attempt)")
        return redirect("/?auth_error=state_mismatch")

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
@login_required
def api_overview():
    """Return standings overview payload for React clients."""
    league_id = _get_league_id()
    payload = _build_overview_payload(_get_standings(league_id), league_id)
    return jsonify(payload)


@app.route("/api/analysis", methods=["GET"])
@login_required
def api_analysis():
    """Return target-category analysis payload for React clients."""
    league_id = _get_league_id()
    payload = _build_analysis_payload(_get_standings(league_id), league_id, request.args.get("team"))
    return jsonify(payload)


@app.route("/api/games-played", methods=["GET"])
@login_required
def api_games_played():
    """Return games played analysis payload for React clients."""
    league_id = _get_league_id()
    params = _parse_games_played_inputs(request.args)
    payload = _build_games_played_payload(_get_standings(league_id), league_id, **params)
    return jsonify(payload)


@app.route("/api/executive-summary", methods=["GET"])
@login_required
def api_executive_summary():
    """Return executive-summary payload for React clients."""
    league_id = _get_league_id()
    params = _parse_games_played_inputs(request.args)
    payload = _build_executive_summary_payload(
        _get_standings(league_id),
        league_id,
        request.args.get("team"),
        **params,
    )
    return jsonify(payload)


@app.route("/api/trends/coverage", methods=["GET"])
@login_required
def api_trends_coverage():
    """Return snapshot coverage info (lightweight check)."""
    league_id = _get_league_id()
    if not league_id:
        return jsonify({"has_data": False})

    from fba.timeseries.snapshots import get_snapshot_range
    coverage = get_snapshot_range(current_user.id, league_id)
    if not coverage:
        return jsonify({"has_data": False})

    first_date, last_date, total_days = coverage
    return jsonify({
        "has_data": total_days >= 2,
        "first_date": first_date,
        "last_date": last_date,
        "total_snapshots": total_days,
    })


@app.route("/api/trends", methods=["GET"])
@login_required
def api_trends():
    """Return scorecard + chart data for the trends page."""
    league_id = _get_league_id()
    standings = _get_standings(league_id)

    if not standings or not standings.get("teams"):
        return jsonify({"has_data": False})

    teams = standings["teams"]
    cat_config_raw = standings.get("league", {}).get("category_config", [])
    cat_configs = from_serializable(cat_config_raw)

    if not cat_configs:
        return jsonify({"has_data": False})

    from fba.timeseries.snapshots import get_snapshot_range
    from fba.timeseries.windowed import compute_chart_data
    from fba.timeseries.scorecard import compute_scorecard
    from fba.normalize import build_per_game_rows

    coverage = get_snapshot_range(current_user.id, league_id)
    if not coverage:
        return jsonify({
            "has_data": False,
            "team_names": [t["team_name"] for t in teams],
        })

    first_date, last_date, total_days = coverage

    # Build season averages from current standings for scorecard comparison
    per_game_rows = build_per_game_rows(teams, cat_configs)
    season_averages: dict[str, dict] = {}
    for row in per_game_rows:
        name = row["team_name"]
        season_averages[name] = {}
        for cfg in cat_configs:
            stat_key = cfg.per_game_key if cfg.per_game_key else cfg.key
            season_averages[name][stat_key] = row.get(stat_key)

    team_names = [t["team_name"] for t in teams]
    selected_team = request.args.get("team", team_names[0] if team_names else "")

    # Build scorecard for selected team
    scorecard = compute_scorecard(
        current_user.id, league_id, selected_team, cat_configs, season_averages,
    )

    # Build chart data for all teams
    chart_data = compute_chart_data(current_user.id, league_id, cat_configs)

    # Build category display info for frontend
    categories = []
    for cfg in cat_configs:
        stat_key = cfg.per_game_key if cfg.per_game_key else cfg.key
        categories.append({
            "key": stat_key,
            "display": cfg.per_game_display,
            "higher_is_better": cfg.higher_is_better,
            "is_percentage": cfg.is_percentage,
        })

    return jsonify({
        "has_data": total_days >= 2,
        "snapshot_coverage": {
            "first_date": first_date,
            "last_date": last_date,
            "total_snapshots": total_days,
        },
        "team_names": team_names,
        "selected_team": selected_team,
        "scorecard": scorecard,
        "chart_data": chart_data,
        "categories": categories,
        "season_averages": season_averages,
    })


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

    cooldown_secs = _check_refresh_rate_limit(current_user.id)
    if cooldown_secs > 0:
        return jsonify({"status": "error", "error": "Please wait before refreshing again.", "retry_after": cooldown_secs}), 429

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

        # Save snapshot for time series (fire-and-forget)
        try:
            from fba.timeseries.snapshots import save_snapshot
            save_snapshot(current_user.id, league_id, data.get("teams", []))
        except Exception:
            logger.warning("Failed to save time series snapshot", exc_info=True)

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
            "error": "Authentication failed. Please log in again.",
            "session_expired": True,
        }), 401

    except YahooAPIError as e:
        logger.error("Yahoo API error: %s", e)
        return jsonify({"status": "error", "error": "Failed to fetch data from Yahoo. Please try again."}), 500

    except Exception as e:
        logger.error("Unexpected error during refresh: %s", e, exc_info=True)
        return jsonify({"status": "error", "error": "An unexpected error occurred. Please try again."}), 500


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
