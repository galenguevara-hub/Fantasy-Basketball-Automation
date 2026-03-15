"""Compute windowed stats by diffing cumulative snapshots."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fba.category_config import CategoryConfig, KNOWN_STATS
from fba.timeseries.snapshots import (
    get_closest_snapshot_date,
    get_snapshots_for_date,
)

# Component stat keys needed for recomputing percentages over windows.
_PCT_COMPONENTS: dict[str, tuple[str, str]] = {
    "FG%": ("FGM", "FGA"),
    "FT%": ("FTM", "FTA"),
}

# Standard windows in days.
STANDARD_WINDOWS = [1, 7, 14, 30]


def _compute_delta(
    current: dict[str, Any],
    past: dict[str, Any],
    category_configs: list[CategoryConfig],
) -> dict[str, Any] | None:
    """Compute per-game deltas between two snapshots for one team.

    Returns a dict with per-game values for counting stats and recomputed
    percentages, or None if the team didn't play in the window.
    """
    gp_current = current.get("gp", 0)
    gp_past = past.get("gp", 0)
    gp_delta = gp_current - gp_past

    cur_stats = current.get("stats", {})
    past_stats = past.get("stats", {})

    result: dict[str, Any] = {
        "team_key": current["team_key"],
        "team_name": current["team_name"],
        "gp_delta": gp_delta,
    }

    for cfg in category_configs:
        if cfg.is_percentage:
            # Recompute from component stat deltas
            components = _PCT_COMPONENTS.get(cfg.key)
            if components:
                made_key, att_key = components
                made_delta = _safe_float(cur_stats.get(made_key, 0)) - _safe_float(past_stats.get(made_key, 0))
                att_delta = _safe_float(cur_stats.get(att_key, 0)) - _safe_float(past_stats.get(att_key, 0))
                result[cfg.key] = made_delta / att_delta if att_delta > 0 else None
            else:
                # For percentages without components (e.g. 3PT%), use current value
                result[cfg.key] = _safe_float(cur_stats.get(cfg.key))
        else:
            # Counting stat: compute per-game in window
            cur_val = _safe_float(cur_stats.get(cfg.key, 0))
            past_val = _safe_float(past_stats.get(cfg.key, 0))
            delta = cur_val - past_val
            pg_key = cfg.per_game_key or cfg.key
            result[pg_key] = delta / gp_delta if gp_delta > 0 else None

    return result


def _safe_float(val: Any) -> float:
    """Convert a value to float, defaulting to 0.0."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def compute_windowed_stats(
    user_id: str,
    league_id: str,
    window_days: int,
    category_configs: list[CategoryConfig],
    *,
    current_date: date | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Compute per-game stats over a window for all teams.

    Returns:
        {
            "available": bool,
            "actual_days": int,
            "window_days": int,
            "teams": [{"team_name", "gp_delta", stat_key: value, ...}, ...]
        }
    """
    today = current_date or date.today()
    target_past = (today - timedelta(days=window_days)).isoformat()
    today_str = today.isoformat()

    # Find closest available snapshot dates
    current_snap_date = get_closest_snapshot_date(
        user_id, league_id, today_str, direction="before", db_path=db_path,
    )
    past_snap_date = get_closest_snapshot_date(
        user_id, league_id, target_past, direction="before", db_path=db_path,
    )

    if not current_snap_date or not past_snap_date or current_snap_date == past_snap_date:
        return {
            "available": False,
            "window_days": window_days,
            "actual_days": 0,
            "teams": [],
        }

    current_snaps = get_snapshots_for_date(user_id, league_id, current_snap_date, db_path=db_path)
    past_snaps = get_snapshots_for_date(user_id, league_id, past_snap_date, db_path=db_path)

    past_by_key = {s["team_key"]: s for s in past_snaps}
    actual_days = (date.fromisoformat(current_snap_date) - date.fromisoformat(past_snap_date)).days

    teams = []
    for cur in current_snaps:
        past = past_by_key.get(cur["team_key"])
        if not past:
            continue
        delta = _compute_delta(cur, past, category_configs)
        if delta:
            teams.append(delta)

    return {
        "available": True,
        "window_days": window_days,
        "actual_days": actual_days,
        "teams": teams,
    }


def compute_all_windows(
    user_id: str,
    league_id: str,
    category_configs: list[CategoryConfig],
    *,
    current_date: date | None = None,
    db_path: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute windowed stats for all standard windows.

    Returns dict keyed by "1d", "7d", "14d", "30d".
    """
    result = {}
    for days in STANDARD_WINDOWS:
        key = f"{days}d"
        result[key] = compute_windowed_stats(
            user_id, league_id, days, category_configs,
            current_date=current_date, db_path=db_path,
        )
    return result


def compute_chart_data(
    user_id: str,
    league_id: str,
    category_configs: list[CategoryConfig],
    *,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Build time series chart data: per-game stats at each snapshot date for all teams.

    Returns a list of {date, teams: [{team_name, stats: {key: value}}]}.
    """
    from fba.timeseries.snapshots import get_all_snapshot_dates, get_snapshots_for_date

    dates = get_all_snapshot_dates(user_id, league_id, db_path=db_path)
    if len(dates) < 2:
        return []

    chart_points = []
    prev_by_team: dict[str, dict[str, Any]] = {}

    for snap_date in dates:
        snaps = get_snapshots_for_date(user_id, league_id, snap_date, db_path=db_path)
        point: dict[str, Any] = {"date": snap_date, "teams": {}}

        for snap in snaps:
            team_name = snap["team_name"]
            stats = snap["stats"]
            gp = snap["gp"]

            team_stats: dict[str, float | None] = {}
            for cfg in category_configs:
                if cfg.is_percentage:
                    # Recompute from components for full precision
                    components = _PCT_COMPONENTS.get(cfg.key)
                    if components:
                        made_key, att_key = components
                        made = _safe_float(stats.get(made_key, 0))
                        att = _safe_float(stats.get(att_key, 0))
                        team_stats[cfg.key] = made / att if att > 0 else None
                    else:
                        team_stats[cfg.key] = _safe_float(stats.get(cfg.key)) or None
                else:
                    # Per-game from season totals
                    val = _safe_float(stats.get(cfg.key, 0))
                    pg_key = cfg.per_game_key or cfg.key
                    team_stats[pg_key] = val / gp if gp > 0 else None

            point["teams"][team_name] = team_stats

        chart_points.append(point)

    return chart_points
