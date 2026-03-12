"""Scorecard: compare a team's recent windows to season average and league best."""

from __future__ import annotations

from datetime import date
from typing import Any

from fba.category_config import CategoryConfig
from fba.timeseries.windowed import compute_all_windows


def compute_scorecard(
    user_id: str,
    league_id: str,
    team_name: str,
    category_configs: list[CategoryConfig],
    season_averages: dict[str, dict[str, float | None]],
    *,
    current_date: date | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Build a scorecard for a team comparing windows to season avg and league best.

    Args:
        season_averages: {team_name: {stat_key: per_game_value}} for all teams.
            Used for the "vs own average" and "vs league best" comparisons.

    Returns:
        {
            "windows": {
                "7d": {
                    "available": bool,
                    "actual_days": int,
                    "categories": {
                        "PTS_pg": {
                            "value": float,
                            "vs_own_avg": float,
                            "vs_league_best": float,
                            "league_best_value": float,
                            "league_best_team": str,
                            "trend": "up" | "down" | "flat",
                        }, ...
                    }
                }, ...
            }
        }
    """
    all_windows = compute_all_windows(
        user_id, league_id, category_configs,
        current_date=current_date, db_path=db_path,
    )

    own_season = season_averages.get(team_name, {})

    scorecard: dict[str, Any] = {"windows": {}}

    for window_key, window_data in all_windows.items():
        if not window_data["available"]:
            scorecard["windows"][window_key] = {
                "available": False,
                "actual_days": 0,
                "categories": {},
            }
            continue

        teams_in_window = window_data["teams"]
        team_row = None
        for t in teams_in_window:
            if t["team_name"] == team_name:
                team_row = t
                break

        if not team_row:
            scorecard["windows"][window_key] = {
                "available": False,
                "actual_days": window_data["actual_days"],
                "categories": {},
            }
            continue

        categories: dict[str, Any] = {}
        for cfg in category_configs:
            stat_key = cfg.per_game_key if cfg.per_game_key else cfg.key
            value = team_row.get(stat_key)

            if value is None:
                categories[stat_key] = {
                    "value": None,
                    "vs_own_avg": None,
                    "vs_league_best": None,
                    "league_best_value": None,
                    "league_best_team": None,
                    "trend": "flat",
                }
                continue

            # vs own season average
            own_avg = own_season.get(stat_key)
            vs_own = (value - own_avg) if own_avg is not None else None
            if not cfg.higher_is_better and vs_own is not None:
                vs_own = -vs_own  # For TO, lower is better so flip sign

            # vs league best in this window
            best_val = None
            best_team = None
            for t in teams_in_window:
                t_val = t.get(stat_key)
                if t_val is None:
                    continue
                if best_val is None:
                    best_val = t_val
                    best_team = t["team_name"]
                elif cfg.higher_is_better and t_val > best_val:
                    best_val = t_val
                    best_team = t["team_name"]
                elif not cfg.higher_is_better and t_val < best_val:
                    best_val = t_val
                    best_team = t["team_name"]

            vs_best = None
            if best_val is not None:
                if cfg.higher_is_better:
                    vs_best = value - best_val
                else:
                    vs_best = best_val - value  # For TO: best is lowest

            categories[stat_key] = {
                "value": round(value, 4) if value is not None else None,
                "vs_own_avg": round(vs_own, 4) if vs_own is not None else None,
                "vs_league_best": round(vs_best, 4) if vs_best is not None else None,
                "league_best_value": round(best_val, 4) if best_val is not None else None,
                "league_best_team": best_team,
                "trend": "flat",  # Will be set below
            }

        # Compute trends: compare shorter window to longer window
        scorecard["windows"][window_key] = {
            "available": True,
            "actual_days": window_data["actual_days"],
            "categories": categories,
        }

    # Set trends by comparing adjacent windows
    window_keys = ["1d", "7d", "14d", "30d"]
    for i, wk in enumerate(window_keys):
        if wk not in scorecard["windows"] or not scorecard["windows"][wk].get("available"):
            continue
        # Compare to next longer window
        longer_wk = window_keys[i + 1] if i + 1 < len(window_keys) else None
        if not longer_wk or longer_wk not in scorecard["windows"]:
            continue
        if not scorecard["windows"][longer_wk].get("available"):
            continue

        for stat_key in scorecard["windows"][wk]["categories"]:
            short_val = scorecard["windows"][wk]["categories"][stat_key]["value"]
            long_val = scorecard["windows"][longer_wk]["categories"].get(stat_key, {}).get("value")
            if short_val is not None and long_val is not None:
                cfg_match = None
                for cfg in category_configs:
                    sk = cfg.per_game_key if cfg.per_game_key else cfg.key
                    if sk == stat_key:
                        cfg_match = cfg
                        break
                if cfg_match:
                    if cfg_match.higher_is_better:
                        trend = "up" if short_val > long_val else ("down" if short_val < long_val else "flat")
                    else:
                        trend = "up" if short_val < long_val else ("down" if short_val > long_val else "flat")
                    scorecard["windows"][wk]["categories"][stat_key]["trend"] = trend

    return scorecard
