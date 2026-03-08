#!/usr/bin/env python3
"""
Executive summary analysis composition.

Builds a decision-oriented payload by combining existing normalized standings,
category gaps, cluster leverage, games-played pace, and projection models.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fba.analysis.category_targets import compute_gaps_and_scores
from fba.analysis.cluster_leverage import compute_cluster_metrics
from fba.analysis.games_played import (
    compute_games_played_metrics,
    compute_projected_roto_ranks,
    compute_projected_totals,
)
from fba.normalize import normalize_standings, parse_stat_value

# Keep category ordering consistent with existing analysis views.
CATEGORY_ORDER = [
    "FG%",
    "FT%",
    "3PM/G",
    "PTS/G",
    "REB/G",
    "AST/G",
    "STL/G",
    "BLK/G",
]

CATEGORY_LABELS = {
    "FG%": "FG%",
    "FT%": "FT%",
    "3PM/G": "3PM",
    "PTS/G": "PTS",
    "REB/G": "REB",
    "AST/G": "AST",
    "STL/G": "STL",
    "BLK/G": "BLK",
}

CATEGORY_RANK_KEYS = {
    "FG%": "FG%_Rank",
    "FT%": "FT%_Rank",
    "3PM/G": "3PM_Rank",
    "PTS/G": "PTS_Rank",
    "REB/G": "REB_Rank",
    "AST/G": "AST_Rank",
    "STL/G": "ST_Rank",
    "BLK/G": "BLK_Rank",
}

CATEGORY_TO_PER_GAME_LABEL = {
    "FG%": "FG%",
    "FT%": "FT%",
    "3PM/G": "3PM/G",
    "PTS/G": "PTS/G",
    "REB/G": "REB/G",
    "AST/G": "AST/G",
    "STL/G": "STL/G",
    "BLK/G": "BLK/G",
}

EPS = 0.05


def _as_float(value: Any) -> Optional[float]:
    """Parse numeric-like values while tolerating None and display placeholders."""
    return parse_stat_value(value)


def _as_int(value: Any) -> Optional[int]:
    """Parse int-ish values."""
    num = _as_float(value)
    if num is None:
        return None
    return int(round(num))


def _ordinal(n: Optional[int]) -> str:
    """Convert integer rank to ordinal string."""
    if n is None:
        return "—"
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _quantile(values: list[float], q: float) -> Optional[float]:
    """Return a simple nearest-rank quantile for small league-sized arrays."""
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    idx = max(0, min(idx, len(ordered) - 1))
    return ordered[idx]


def _mean(values: list[float]) -> Optional[float]:
    """Safe mean helper."""
    if not values:
        return None
    return sum(values) / len(values)


def _category_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    """Deterministic sort for category rows."""
    category = str(item.get("category", ""))
    try:
        idx = CATEGORY_ORDER.index(category)
    except ValueError:
        idx = len(CATEGORY_ORDER)
    return (idx, category)


def _empty_payload() -> dict[str, Any]:
    """Return an empty summary payload."""
    return {
        "team_names": [],
        "selected_team": None,
        "summary_card": {
            "standings_line": "",
            "performance_line": "",
            "opportunities": [],
            "risks": [],
            "pace_line": "",
            "competition_line": "",
        },
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
    }


def _format_ordinal(value: Optional[int]) -> Optional[str]:
    """Return ordinal string for display fields."""
    if value is None:
        return None
    return _ordinal(value)


def build_executive_summary(
    teams: list[dict[str, Any]],
    selected_team: Optional[str],
    start_date: date,
    end_date: date,
    today_date: date,
    total_games: int = 816,
) -> dict[str, Any]:
    """
    Compose a full executive-summary payload from existing analysis models.

    This function intentionally centralizes expensive calculations so the
    frontend can render a decision dashboard from one API request.
    """
    if not teams:
        return _empty_payload()

    normalized = normalize_standings(teams)
    per_game_rows = normalized.get("per_game_rows", [])
    ranking_rows = normalized.get("ranking_rows", [])
    team_names = [str(r.get("team_name")) for r in per_game_rows if r.get("team_name")]

    if selected_team not in team_names and team_names:
        selected_team = team_names[0]
    if not selected_team:
        payload = _empty_payload()
        payload["team_names"] = team_names
        return payload

    team_by_name: dict[str, dict[str, Any]] = {
        str(team.get("team_name")): team for team in teams if team.get("team_name")
    }
    ranking_by_name: dict[str, dict[str, Any]] = {
        str(row.get("team_name")): row for row in ranking_rows if row.get("team_name")
    }

    analysis_all = compute_gaps_and_scores(per_game_rows)
    cluster_all = compute_cluster_metrics(per_game_rows)
    selected_analysis = analysis_all.get(selected_team, [])
    selected_cluster = cluster_all.get(selected_team, {})

    pace_rows, pace_date_valid = compute_games_played_metrics(
        teams, start_date, end_date, today_date, total_games=total_games
    )
    pace_by_team = {str(row.get("team_name")): row for row in pace_rows if row.get("team_name")}

    projected_totals = compute_projected_totals(
        teams, start_date, end_date, today_date, total_games=total_games
    )
    projected_totals_by_team = {
        str(row.get("team_name")): row for row in projected_totals if row.get("team_name")
    }

    projected_ranks = compute_projected_roto_ranks(projected_totals, teams)
    projected_ranks_by_team = {
        str(row.get("team_name")): row for row in projected_ranks if row.get("team_name")
    }

    valid_pg_rows = [row for row in ranking_rows if _as_float(row.get("rank_total")) is not None]
    valid_pg_rows.sort(
        key=lambda row: (
            -(_as_float(row.get("rank_total")) or 0.0),
            str(row.get("team_name", "")),
        )
    )
    per_game_rank_by_team = {str(row["team_name"]): idx + 1 for idx, row in enumerate(valid_pg_rows)}

    # ------------------------------------------------------------------
    # Per-game vs raw standings comparison
    # ------------------------------------------------------------------
    per_game_vs_raw_rows: list[dict[str, Any]] = []
    for name in team_names:
        raw_team = team_by_name.get(name, {})
        ranking_row = ranking_by_name.get(name, {})
        raw_rank = _as_int(raw_team.get("rank"))
        pg_rank = per_game_rank_by_team.get(name)
        difference = (raw_rank - pg_rank) if raw_rank is not None and pg_rank is not None else None
        per_game_vs_raw_rows.append(
            {
                "team_name": name,
                "raw_roto_rank": raw_rank,
                "per_game_rank": pg_rank,
                "difference": difference,
                "current_points": _as_float(raw_team.get("total_points")),
                "per_game_points": _as_float(ranking_row.get("rank_total")),
                "points_delta": _as_float(ranking_row.get("points_delta")),
                "is_selected": name == selected_team,
            }
        )

    per_game_vs_raw_rows.sort(
        key=lambda row: (
            row.get("raw_roto_rank") if row.get("raw_roto_rank") is not None else 999,
            row.get("team_name", ""),
        )
    )

    selected_rank_row = ranking_by_name.get(selected_team, {})
    selected_points_delta = _as_float(selected_rank_row.get("points_delta"))
    if selected_points_delta is None:
        per_game_vs_raw_label = None
    elif selected_points_delta < -0.05:
        per_game_vs_raw_label = (
            f"Your standings are inflated by {abs(selected_points_delta):.1f} points due to games played advantage."
        )
    elif selected_points_delta > 0.05:
        per_game_vs_raw_label = (
            f"Your standings are suppressed by {abs(selected_points_delta):.1f} points due to games played deficit."
        )
    else:
        per_game_vs_raw_label = "Your standings are closely aligned with your per-game profile."

    # ------------------------------------------------------------------
    # Category stability + opportunities / leverage
    # ------------------------------------------------------------------
    sigma_values = [
        _as_float(metrics.get("sigma"))
        for metrics in selected_cluster.values()
        if isinstance(metrics, dict) and _as_float(metrics.get("sigma")) is not None
    ]
    sigma_q25 = _quantile([v for v in sigma_values if v is not None], 0.25)
    sigma_q75 = _quantile([v for v in sigma_values if v is not None], 0.75)

    category_stability: list[dict[str, Any]] = []
    category_opportunities: list[dict[str, Any]] = []
    for row in sorted(selected_analysis, key=_category_sort_key):
        category = str(row.get("category", ""))
        display = CATEGORY_LABELS.get(category, str(row.get("display", category)).replace("/G", ""))
        cluster_metrics = selected_cluster.get(category, {}) if isinstance(selected_cluster, dict) else {}
        sigma = _as_float(cluster_metrics.get("sigma")) if isinstance(cluster_metrics, dict) else None

        if sigma is None:
            volatility = "Unknown"
        elif sigma_q75 is not None and sigma >= sigma_q75:
            volatility = "Unstable"
        elif sigma_q25 is not None and sigma <= sigma_q25:
            volatility = "Stable"
        else:
            volatility = "Moderate"

        z_gap_up = _as_float(row.get("z_gap_up"))
        points_available = _as_int(cluster_metrics.get("points_up_within_T")) if isinstance(cluster_metrics, dict) else 0
        points_available = points_available or 0
        if z_gap_up is None:
            leverage_score = 0.0
        elif z_gap_up == 0:
            leverage_score = points_available / EPS
        else:
            leverage_score = max(points_available, 1) / max(z_gap_up, EPS)

        category_stability.append(
            {
                "category": display,
                "sigma": sigma,
                "volatility": volatility,
            }
        )

        category_opportunities.append(
            {
                "category": display,
                "raw_category": category,
                "gap_to_gain_1": _as_float(row.get("gap_up")),
                "gap_to_lose_1": _as_float(row.get("gap_down")),
                "z_gap_up": z_gap_up,
                "z_gap_down": _as_float(row.get("z_gap_down")),
                "points_available": points_available,
                "leverage_score": leverage_score,
                "roi_score": "Low",
                "is_target": bool(row.get("is_target")),
                "is_defend": bool(row.get("is_defend")),
                "rank": _as_int(row.get("rank")),
                "volatility": volatility,
            }
        )

    scorable = [row for row in category_opportunities if row.get("z_gap_up") is not None]
    scorable.sort(
        key=lambda row: (
            -(row.get("leverage_score") or 0.0),
            row.get("z_gap_up") if row.get("z_gap_up") is not None else 999.0,
            row.get("category", ""),
        )
    )
    for idx, row in enumerate(scorable):
        if idx < 3:
            row["roi_score"] = "High"
        elif idx < 6:
            row["roi_score"] = "Medium"
        else:
            row["roi_score"] = "Low"

    best_categories_to_target = sorted(
        [row for row in category_opportunities if row.get("z_gap_up") is not None],
        key=lambda row: (
            row.get("z_gap_up") if row.get("z_gap_up") is not None else 999.0,
            -(row.get("z_gap_down") or 0.0),
            -(row.get("leverage_score") or 0.0),
        ),
    )[:3]

    categories_at_risk = sorted(
        [row for row in category_opportunities if row.get("z_gap_down") is not None],
        key=lambda row: (
            row.get("z_gap_down") if row.get("z_gap_down") is not None else 999.0,
            row.get("category", ""),
        ),
    )[:3]

    # ------------------------------------------------------------------
    # Multi-point swing opportunities
    # ------------------------------------------------------------------
    multi_point_swings: list[dict[str, Any]] = []
    for row in category_opportunities:
        raw_category = str(row.get("raw_category", ""))
        cluster_metrics = selected_cluster.get(raw_category, {}) if isinstance(selected_cluster, dict) else {}
        if not isinstance(cluster_metrics, dict):
            continue

        potential_swing = _as_int(cluster_metrics.get("points_up_within_T")) or 0
        if potential_swing <= 0:
            continue

        category_label = str(row.get("category", raw_category))
        multi_point_swings.append(
            {
                "category": category_label,
                "raw_category": raw_category,
                "potential_swing": potential_swing,
                "effort_z": _as_float(cluster_metrics.get("z_to_gain_1")),
                "up_score": _as_float(cluster_metrics.get("cluster_up_score")),
                "headline": (
                    f"{category_label} could swing +{potential_swing} roto point"
                    f"{'' if potential_swing == 1 else 's'} with modest improvement."
                ),
            }
        )

    multi_point_swings.sort(
        key=lambda row: (
            -(row.get("potential_swing") or 0),
            -(row.get("up_score") or 0.0),
            row.get("category", ""),
        )
    )

    # ------------------------------------------------------------------
    # Games-played pace and nearby-team context
    # ------------------------------------------------------------------
    selected_team_row = team_by_name.get(selected_team, {})
    selected_points = _as_float(selected_team_row.get("total_points"))
    selected_rank = _as_int(selected_team_row.get("rank"))
    selected_gp = _as_int(selected_team_row.get("stats", {}).get("GP"))

    selected_pace = pace_by_team.get(selected_team, {})
    current_pace = _as_float(selected_pace.get("avg_gp_per_day_so_far"))
    remaining_days = _as_int(selected_pace.get("remaining_days"))
    selected_projected_gp = _as_float(projected_totals_by_team.get(selected_team, {}).get("projected_gp"))

    league_avg_pace = _mean(
        [val for val in (_as_float(row.get("avg_gp_per_day_so_far")) for row in pace_rows) if val is not None]
    )
    league_avg_projected_gp = _mean(
        [val for val in (_as_float(row.get("projected_gp")) for row in projected_totals) if val is not None]
    )
    projected_gp_delta_vs_avg = (
        selected_projected_gp - league_avg_projected_gp
        if selected_projected_gp is not None and league_avg_projected_gp is not None
        else None
    )

    needed_gp_per_day_to_hit_cap = None
    if (
        selected_gp is not None
        and remaining_days is not None
        and remaining_days > 0
    ):
        needed_gp_per_day_to_hit_cap = max(total_games - selected_gp, 0) / remaining_days

    recommended_pace_adjustment = 0.0
    if (
        current_pace is not None
        and needed_gp_per_day_to_hit_cap is not None
        and needed_gp_per_day_to_hit_cap > current_pace
    ):
        recommended_pace_adjustment = needed_gp_per_day_to_hit_cap - current_pace

    games_pace = {
        "date_valid": pace_date_valid,
        "current_pace": current_pace,
        "projected_final_games_played": selected_projected_gp,
        "league_avg_pace": league_avg_pace,
        "league_avg_projected_gp": league_avg_projected_gp,
        "projected_gp_delta_vs_avg": projected_gp_delta_vs_avg,
        "current_games_played": selected_gp,
        "remaining_days": remaining_days,
        "max_allowed_games": total_games,
        "needed_gp_per_day_to_hit_cap": needed_gp_per_day_to_hit_cap,
        "recommended_pace_adjustment": recommended_pace_adjustment,
    }

    # Team neighborhood from per-game rankings only (selected + 3 closest teams).
    teams_by_rank = sorted(
        teams,
        key=lambda team: (
            _as_int(team.get("rank")) if _as_int(team.get("rank")) is not None else 999,
            str(team.get("team_name", "")),
        ),
    )
    pg_ranked_names = [str(row.get("team_name", "")) for row in valid_pg_rows if row.get("team_name")]
    selected_pg_rank = per_game_rank_by_team.get(selected_team)
    selected_pg_index = pg_ranked_names.index(selected_team) if selected_team in pg_ranked_names else None
    nearby_pg_names: list[str] = []
    if selected_pg_index is not None:
        candidates = []
        for idx, name in enumerate(pg_ranked_names):
            if name == selected_team:
                continue
            candidates.append((abs(idx - selected_pg_index), idx, name))
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        nearby_pg_names = [name for _, _, name in candidates[:3]]

    nearby_names = [selected_team, *nearby_pg_names]
    above_team_name = None
    below_team_name = None
    for idx, team in enumerate(teams_by_rank):
        if str(team.get("team_name")) == selected_team:
            if idx > 0:
                above_team_name = str(teams_by_rank[idx - 1].get("team_name"))
            if idx + 1 < len(teams_by_rank):
                below_team_name = str(teams_by_rank[idx + 1].get("team_name"))
            break

    nearby_teams: list[dict[str, Any]] = []
    for name in nearby_names:
        team = team_by_name.get(name, {})
        nearby_teams.append(
            {
                "team_name": name,
                "roto_rank": _as_int(team.get("rank")),
                "per_game_rank": per_game_rank_by_team.get(name),
                "current_points": _as_float(team.get("total_points")),
                "games_played": _as_int(team.get("stats", {}).get("GP")),
                "projected_gp": _as_float(projected_totals_by_team.get(name, {}).get("projected_gp")),
                "is_selected": name == selected_team,
            }
        )
    nearby_teams.sort(
        key=lambda row: (
            row.get("per_game_rank") if row.get("per_game_rank") is not None else 999,
            row.get("team_name", ""),
        )
    )

    nearby_team_insights: list[str] = []
    nearby_team_metric: Optional[str] = None
    if above_team_name and selected_gp is not None:
        above_gp = _as_int(team_by_name.get(above_team_name, {}).get("stats", {}).get("GP"))
        if above_gp is not None and (above_gp - selected_gp) >= 15:
            nearby_team_insights.append(
                f"{above_team_name} has a sizable games-played edge that could narrow late in the season."
            )
            nearby_team_metric = f"GP gap {above_gp - selected_gp:+d}"
    if below_team_name and selected_projected_gp is not None:
        below_proj_gp = _as_float(projected_totals_by_team.get(below_team_name, {}).get("projected_gp"))
        if below_proj_gp is not None and (below_proj_gp - selected_projected_gp) >= 10:
            nearby_team_insights.append(
                f"{below_team_name} has a higher projected GP ({below_proj_gp:.0f} vs {selected_projected_gp:.0f})."
            )
            nearby_team_metric = f"Proj GP gap {below_proj_gp - selected_projected_gp:+.0f}"
    if not nearby_team_insights and below_team_name:
        nearby_team_insights.append(f"Watch {below_team_name} closely in nearby categories this week.")
        selected_pg = per_game_rank_by_team.get(selected_team)
        below_pg = per_game_rank_by_team.get(below_team_name)
        if selected_pg is not None and below_pg is not None:
            nearby_team_metric = f"PG rank gap {abs(selected_pg - below_pg)}"

    # ------------------------------------------------------------------
    # Projected final standings
    # ------------------------------------------------------------------
    projected_standings: list[dict[str, Any]] = []
    for team in teams:
        name = str(team.get("team_name", ""))
        proj = projected_ranks_by_team.get(name, {})
        projected_standings.append(
            {
                "team_name": name,
                "current_rank": _as_int(team.get("rank")),
                "current_points": _as_float(team.get("total_points")),
                "projected_points": _as_float(proj.get("projected_total")),
                "projected_rank": None,  # filled after sorting
                "is_selected": name == selected_team,
            }
        )

    projected_standings.sort(
        key=lambda row: (
            -(row.get("projected_points") or 0.0),
            row.get("team_name", ""),
        )
    )
    projected_finish: Optional[int] = None
    for idx, row in enumerate(projected_standings, start=1):
        row["projected_rank"] = idx
        if row.get("is_selected"):
            projected_finish = idx

    # ------------------------------------------------------------------
    # Category competition map for nearby teams
    # ------------------------------------------------------------------
    nearby_points_names = [name for name in nearby_pg_names if name != selected_team]
    selected_rank_row_data = ranking_by_name.get(selected_team, {})

    category_competition: list[dict[str, Any]] = []
    for category in CATEGORY_ORDER:
        rank_key = CATEGORY_RANK_KEYS.get(category)
        if not rank_key:
            continue
        selected_cat_rank = _as_float(selected_rank_row_data.get(rank_key))
        competitors: list[str] = []
        for name in nearby_points_names:
            team_rank_row = ranking_by_name.get(name, {})
            competitor_rank = _as_float(team_rank_row.get(rank_key))
            if selected_cat_rank is None or competitor_rank is None:
                continue
            if abs(competitor_rank - selected_cat_rank) <= 2:
                competitors.append(name)

        competitors.sort()
        intensity_score = len(competitors)
        if intensity_score >= 3:
            intensity = "High"
        elif intensity_score == 2:
            intensity = "Medium"
        elif intensity_score == 1:
            intensity = "Low"
        else:
            intensity = "Minimal"

        category_competition.append(
            {
                "category": CATEGORY_LABELS.get(category, category),
                "intensity": intensity,
                "intensity_score": intensity_score,
                "competitors": competitors,
                "competitor_text": ", ".join(competitors) if competitors else "minimal overlap",
                "method": "Nearby teams are the 3 closest per-game ranks; overlap = category rank difference <= 2.",
            }
        )

    high_leverage_categories = [
        row["category"]
        for row in category_competition
        if row.get("intensity_score", 0) >= 2
        and any(
            target.get("category") == row.get("category")
            for target in best_categories_to_target
        )
    ]

    # ------------------------------------------------------------------
    # Trade hints, actionable bullets, and summary card text
    # ------------------------------------------------------------------
    weakest_categories = sorted(
        [row for row in category_opportunities if row.get("rank") is not None],
        key=lambda row: (row.get("rank") if row.get("rank") is not None else 999, row.get("category", "")),
    )[:2]
    trade_hints = [str(row.get("category")) for row in weakest_categories if row.get("category")]

    actionable_insights: list[dict[str, Any]] = []
    if best_categories_to_target:
        focus_rows = best_categories_to_target[:2]
        focus = [str(row.get("category")) for row in focus_rows]
        z_values = [row.get("z_gap_up") for row in focus_rows if _as_float(row.get("z_gap_up")) is not None]
        avg_z = sum(float(v) for v in z_values) / len(z_values) if z_values else None
        actionable_insights.append({
            "text": "Focus on lowest-effort point gains",
            "categories": focus,
            "metric": f"avg z+ {avg_z:.2f}" if avg_z is not None else None,
        })
    if categories_at_risk:
        risk_row = categories_at_risk[0]
        risk_val = _as_float(risk_row.get("z_gap_down"))
        actionable_insights.append({
            "text": "Protect your thinnest buffer",
            "categories": [str(risk_row.get("category"))],
            "metric": f"z− {risk_val:.2f}" if risk_val is not None else None,
        })
    if recommended_pace_adjustment > 0.05:
        actionable_insights.append({
            "text": "Increase games played pace",
            "categories": [],
            "metric": f"+{recommended_pace_adjustment:.2f} GP/day",
        })
    if multi_point_swings:
        swing_row = multi_point_swings[0]
        actionable_insights.append({
            "text": "Prioritize your top cluster swing",
            "categories": [str(swing_row.get("category"))],
            "metric": f"+{int(swing_row.get('potential_swing') or 0)} pts",
        })
    if nearby_team_insights:
        actionable_insights.append({
            "text": nearby_team_insights[0],
            "categories": [],
            "metric": nearby_team_metric,
        })
    if trade_hints:
        actionable_insights.append({
            "text": "Trade/waiver construction: prioritize category fit",
            "categories": trade_hints,
            "metric": f"{len(trade_hints)} weak categories",
        })

    # De-duplicate while preserving order and keep concise.
    deduped_insights: list[dict[str, Any]] = []
    dedupe_seen: set[str] = set()
    for insight in actionable_insights:
        text = str(insight.get("text", "")).strip()
        if not text or text in dedupe_seen:
            continue
        dedupe_seen.add(text)
        deduped_insights.append(insight)
    actionable_insights = deduped_insights[:6]

    current_points = _as_float(selected_team_row.get("total_points"))
    per_game_rank = per_game_rank_by_team.get(selected_team)
    performance_line: str
    if selected_rank is not None and per_game_rank is not None and per_game_rank < selected_rank:
        performance_line = (
            f"Your roster is performing like a {_ordinal(per_game_rank)} place team on a per-game basis,"
            " but your current rank is slightly deflated by games played."
        )
    elif selected_rank is not None and per_game_rank is not None and per_game_rank > selected_rank:
        performance_line = (
            f"Your raw position is ahead of your {_ordinal(per_game_rank)} place per-game profile,"
            " supported by a games played advantage."
        )
    else:
        performance_line = "Your per-game profile is closely aligned with your current standing."

    if recommended_pace_adjustment > 0:
        pace_line = (
            f"You are projected for {selected_projected_gp:.0f} games versus the {total_games} cap."
            f" Increasing pace by ~{recommended_pace_adjustment:.2f} GP/day would close most of that gap."
        )
    elif projected_gp_delta_vs_avg is not None and projected_gp_delta_vs_avg > 0:
        pace_line = (
            f"You are projected to finish about {projected_gp_delta_vs_avg:.0f} games above the league average."
            " Protect efficiency categories while managing volume."
        )
    else:
        pace_line = "Your games-played pace is close to the league baseline."

    nearby_names_for_text = [row["team_name"] for row in nearby_teams if not row.get("is_selected")]
    competition_targets = high_leverage_categories or [
        str(row.get("category")) for row in best_categories_to_target[:2]
    ]
    if nearby_names_for_text and competition_targets:
        competition_line = (
            f"The teams closest to you ({', '.join(nearby_names_for_text[:3])})"
            f" are also clustered in {', '.join(competition_targets[:2])}, making those categories high leverage."
        )
    else:
        competition_line = "Category competition is broadly distributed with no single bottleneck."

    summary_card = {
        "standings_line": (
            f"You are currently {_ordinal(selected_rank)} in the league with "
            f"{current_points:.1f} roto points."
            if selected_rank is not None and current_points is not None
            else "Current standing data is unavailable."
        ),
        "performance_line": performance_line,
        "opportunities": [
            {
                "category": row.get("category"),
                "gap_to_gain_1": row.get("gap_to_gain_1"),
            }
            for row in best_categories_to_target[:2]
        ],
        "risks": [
            {
                "category": row.get("category"),
                "gap_to_lose_1": row.get("gap_to_lose_1"),
            }
            for row in categories_at_risk[:2]
        ],
        "pace_line": pace_line,
        "competition_line": competition_line,
        "expected_equal_gp_rank": per_game_rank,
        "expected_equal_gp_rank_ordinal": _format_ordinal(per_game_rank),
        "games_left_line": (
            f"{remaining_days} days left. Lean into cluster targets with the highest multi-point swing first."
            if remaining_days is not None
            else ""
        ),
    }

    # Add concrete full-swing improvement values for each multi-point row.
    for swing in multi_point_swings:
        raw_category = str(swing.get("raw_category", ""))
        cluster_metrics = selected_cluster.get(raw_category, {}) if isinstance(selected_cluster, dict) else {}
        sigma = _as_float(cluster_metrics.get("sigma")) if isinstance(cluster_metrics, dict) else None
        z_up_max = _as_float(cluster_metrics.get("z_up_max")) if isinstance(cluster_metrics, dict) else None
        if sigma is not None and z_up_max is not None:
            swing_value = sigma * z_up_max
        else:
            swing_value = None
        swing["full_swing_z"] = z_up_max
        swing["full_swing_improvement"] = swing_value
        unit = CATEGORY_TO_PER_GAME_LABEL.get(raw_category, str(swing.get("category")))
        if swing_value is not None:
            swing["full_swing_text"] = f"+{swing_value:.3f} {unit} (z {z_up_max:.2f})"
        else:
            swing["full_swing_text"] = "—"

    return {
        "team_names": team_names,
        "selected_team": selected_team,
        "summary_card": summary_card,
        "per_game_vs_raw_rows": per_game_vs_raw_rows,
        "per_game_vs_raw_label": per_game_vs_raw_label,
        "category_opportunities": category_opportunities,
        "best_categories_to_target": best_categories_to_target,
        "categories_at_risk": categories_at_risk,
        "multi_point_swings": multi_point_swings,
        "games_pace": games_pace,
        "nearby_teams": nearby_teams,
        "nearby_team_insights": nearby_team_insights,
        "projected_standings": projected_standings,
        "projected_finish": projected_finish,
        "category_competition": category_competition,
        "category_stability": category_stability,
        "high_leverage_categories": high_leverage_categories,
        "actionable_insights": actionable_insights,
        "trade_hints": trade_hints,
        "momentum": {
            "available": False,
            "message": "Historical snapshots are not available in the current dataset.",
        },
    }
