#!/usr/bin/env python3
"""
Category Targets Analysis — Layer 1: Marginal Gain + Standardized Effort.

For each team and category, computes:
- z-gap to gain +1 roto point (effort)
- z-buffer before losing -1 roto point (risk)
- Target Score ranking categories by ROI
- Recommendation tags (TARGET / DEFEND)

All computations use per-game normalized stats (and raw % for FG/FT).
No web dependencies — pure data logic.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from fba.category_config import (
    CategoryConfig,
    DEFAULT_8CAT_CONFIG,
    get_analysis_keys,
)


# Legacy constant — derived from DEFAULT_8CAT_CONFIG for backward compat.
CATEGORIES: list[dict[str, str]] = get_analysis_keys(DEFAULT_8CAT_CONFIG)

# Cap for score when z_gap_up == 0 (exact tie with team above).
TIE_SCORE_CAP = 1000.0

# Weight for risk component in target score.
RISK_WEIGHT = 0.25

# Weight for defensive score when team is already in 1st place.
DEFEND_WEIGHT = 0.8

# Floor to prevent division by zero in score calculations.
EPS = 0.05

# Number of categories to tag as TARGET / DEFEND.
N_TARGETS = 3
N_DEFEND = 3


def compute_category_sigma(
    rows: List[Dict[str, Any]],
    category_config: Optional[List[CategoryConfig]] = None,
) -> Dict[str, Optional[float]]:
    """
    Compute population std dev (ddof=0) for each category across teams.

    Args:
        rows: List of per-game row dicts (from normalize.build_per_game_rows).
        category_config: Optional dynamic config.

    Returns:
        Dict mapping category key -> sigma (float), or None if non-actionable
        (all values missing or zero variance).
    """
    cats = get_analysis_keys(category_config) if category_config else CATEGORIES
    sigmas: Dict[str, Optional[float]] = {}

    for cat in cats:
        key = cat["key"]
        values = [row[key] for row in rows if row.get(key) is not None]

        if len(values) < 2:
            sigmas[key] = None
            continue

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        sigma = math.sqrt(variance)

        sigmas[key] = sigma if sigma > 0 else None

    return sigmas


def _sorted_teams_for_category(
    rows: List[Dict[str, Any]],
    key: str,
    higher_is_better: bool = True,
) -> List[Dict[str, Any]]:
    """
    Sort teams by a category value, best first.
    Teams with None values are excluded.
    Tie-break by team_name ascending for stability.

    For higher-is-better categories, sorts descending.
    For lower-is-better categories (e.g. TO), sorts ascending.
    """
    valid = [r for r in rows if r.get(key) is not None]
    if higher_is_better:
        return sorted(valid, key=lambda r: (-r[key], r["team_name"]))
    else:
        return sorted(valid, key=lambda r: (r[key], r["team_name"]))


def compute_gaps_and_scores(
    rows: List[Dict[str, Any]],
    category_config: Optional[List[CategoryConfig]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compute gap-to-gain, buffer-to-lose, target score, and recommendations
    for every team across all active categories.

    Respects category directionality: for lower-is-better categories (e.g. TO),
    "better" means a lower value and "gap_up" is how much you need to decrease.

    Args:
        rows: List of per-game row dicts.
        category_config: Optional dynamic config.

    Returns:
        Dict keyed by team_name, each value is a list of category analysis dicts.
    """
    if not rows:
        return {}

    cats = get_analysis_keys(category_config) if category_config else CATEGORIES
    sigmas = compute_category_sigma(rows, category_config)

    # Pre-compute sorted order and ranks per category.
    sorted_by_cat: Dict[str, List[Dict[str, Any]]] = {}
    ranks_by_cat: Dict[str, Dict[str, int]] = {}

    for cat in cats:
        key = cat["key"]
        hib = cat.get("higher_is_better", True)
        sorted_teams = _sorted_teams_for_category(rows, key, hib)
        sorted_by_cat[key] = sorted_teams

        # Assign ranks: best = N (number of teams with values), worst = 1.
        n = len(sorted_teams)
        ranks: Dict[str, int] = {}
        for pos, team_row in enumerate(sorted_teams):
            ranks[team_row["team_name"]] = n - pos
        ranks_by_cat[key] = ranks

    # Build analysis for each team.
    result: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        team_name = row["team_name"]
        cat_analyses: List[Dict[str, Any]] = []

        for cat in cats:
            key = cat["key"]
            hib = cat.get("higher_is_better", True)
            value = row.get(key)
            sigma = sigmas.get(key)
            sorted_teams = sorted_by_cat[key]
            ranks = ranks_by_cat[key]

            rank = ranks.get(team_name)

            if value is None:
                cat_analyses.append(_none_entry(cat, rank))
                continue

            # Find position of this team in the sorted list.
            team_pos = None
            for i, t in enumerate(sorted_teams):
                if t["team_name"] == team_name:
                    team_pos = i
                    break

            if team_pos is None:
                cat_analyses.append(_none_entry(cat, rank))
                continue

            # --- Gap up (effort): find nearest team ranked above ---
            # In sorted list, positions 0..team_pos-1 are better-ranked teams.
            # A team directly above in sort order counts even if its value
            # is the same (Yahoo rounds percentages, hiding micro-gaps).
            next_better_team = None
            next_better_value = None
            gap_up = None
            z_gap_up = None

            if team_pos > 0:
                candidate = sorted_teams[team_pos - 1]
                next_better_team = candidate["team_name"]
                next_better_value = candidate[key]
                gap_up = abs(next_better_value - value)

            if gap_up is not None and sigma is not None and sigma > 0:
                z_gap_up = gap_up / sigma

            # --- Gap down (risk): find nearest team ranked below ---
            next_worse_team = None
            next_worse_value = None
            gap_down = None
            z_gap_down = None

            if team_pos < len(sorted_teams) - 1:
                candidate = sorted_teams[team_pos + 1]
                next_worse_team = candidate["team_name"]
                next_worse_value = candidate[key]
                gap_down = abs(value - next_worse_value)

            if gap_down is not None and sigma is not None and sigma > 0:
                z_gap_down = gap_down / sigma

            # --- Target Score ---
            target_score = _compute_target_score(z_gap_up, z_gap_down)

            cat_analyses.append({
                "category": cat["name"],
                "display": cat["display"],
                "key": key,
                "value": value,
                "rank": rank,
                "next_better_team": next_better_team,
                "next_better_value": next_better_value,
                "gap_up": gap_up,
                "z_gap_up": z_gap_up,
                "next_worse_team": next_worse_team,
                "next_worse_value": next_worse_value,
                "gap_down": gap_down,
                "z_gap_down": z_gap_down,
                "target_score": target_score,
                "tag": None,
                "is_target": False,
                "is_defend": False,
            })

        # --- Assign recommendation tags ---
        _assign_tags(cat_analyses)

        result[team_name] = cat_analyses

    return result


def _none_entry(cat: dict, rank: Optional[int]) -> dict:
    """Build a category entry where all computed fields are None."""
    return {
        "category": cat["name"],
        "display": cat["display"],
        "key": cat["key"],
        "value": None,
        "rank": rank,
        "next_better_team": None,
        "next_better_value": None,
        "gap_up": None,
        "z_gap_up": None,
        "next_worse_team": None,
        "next_worse_value": None,
        "gap_down": None,
        "z_gap_down": None,
        "target_score": None,
        "tag": None,
        "is_target": False,
        "is_defend": False,
    }


def _compute_target_score(
    z_gap_up: Optional[float],
    z_gap_down: Optional[float],
) -> Optional[float]:
    """
    Compute the target score (ROI-like) for a category.

    For non-first-place categories:
        score = effort_component + 0.25 * risk_component
        effort_component = 1 / max(z_gap_up, EPS)
        risk_component   = z_gap_down (if exists, else 0)

    For first-place categories (z_gap_up is None):
        score = DEFEND_WEIGHT / max(z_gap_down, EPS)
        Fragile leads (small z_gap_down) get a higher score so they
        can still be prioritised as defensive categories.

    If z_gap_up == 0 → tie with team above, cap effort at TIE_SCORE_CAP.
    Returns None only when both z_gap_up and z_gap_down are None
    (e.g. solo league or missing data).
    """
    if z_gap_up is None:
        if z_gap_down is None:
            return None
        return DEFEND_WEIGHT / max(z_gap_down, EPS)

    if z_gap_up == 0:
        effort = TIE_SCORE_CAP
    else:
        effort = 1.0 / z_gap_up

    risk = z_gap_down if z_gap_down is not None else 0.0

    return effort + RISK_WEIGHT * risk


def compute_gap_chart_data(
    rows: List[Dict[str, Any]],
    selected_team: str,
    category_config: Optional[List[CategoryConfig]] = None,
) -> List[Dict[str, Any]]:
    """
    Build per-category data for the Category Gap Bar Chart.

    For each category, returns the selected team's value + z-score,
    the nearest team above/below with their values + z-scores,
    and the league min/max for both per-game and z-score modes.

    Z-scores are computed as (value - mean) / sigma for each team.
    """
    if not rows:
        return []

    configs = category_config if category_config else DEFAULT_8CAT_CONFIG
    cats = get_analysis_keys(configs)
    sigmas = compute_category_sigma(rows, configs)

    # Build is_percentage lookup from the full config objects
    pct_lookup: Dict[str, bool] = {}
    for c in configs:
        analysis_key = c.per_game_key if c.per_game_key else c.key
        pct_lookup[analysis_key] = c.is_percentage

    # Pre-compute means for z-score calculation
    means: Dict[str, float] = {}
    for cat in cats:
        key = cat["key"]
        values = [row[key] for row in rows if row.get(key) is not None]
        if values:
            means[key] = sum(values) / len(values)

    # Compute z-scores for all teams
    team_zscores: Dict[str, Dict[str, Optional[float]]] = {}
    for row in rows:
        name = row["team_name"]
        zs: Dict[str, Optional[float]] = {}
        for cat in cats:
            key = cat["key"]
            val = row.get(key)
            sigma = sigmas.get(key)
            if val is not None and sigma is not None and sigma > 0 and key in means:
                zs[key] = (val - means[key]) / sigma
            else:
                zs[key] = None
        team_zscores[name] = zs

    chart_rows: List[Dict[str, Any]] = []

    for cat in cats:
        key = cat["key"]
        hib = cat.get("higher_is_better", True)

        # Collect all valid per-game values
        all_values = [row[key] for row in rows if row.get(key) is not None]
        all_zscores = [
            team_zscores[row["team_name"]][key]
            for row in rows
            if team_zscores.get(row["team_name"], {}).get(key) is not None
        ]

        if not all_values:
            continue

        league_min = min(all_values)
        league_max = max(all_values)
        z_min = min(all_zscores) if all_zscores else None
        z_max = max(all_zscores) if all_zscores else None

        # Find the selected team's row
        my_row = next((r for r in rows if r["team_name"] == selected_team), None)
        if my_row is None or my_row.get(key) is None:
            continue

        my_value = my_row[key]
        my_zscore = team_zscores.get(selected_team, {}).get(key)

        # Sort teams best-first to find neighbors
        sorted_teams = _sorted_teams_for_category(rows, key, hib)
        my_pos = next(
            (i for i, t in enumerate(sorted_teams) if t["team_name"] == selected_team),
            None,
        )
        if my_pos is None:
            continue

        # Find nearest team above (next better-ranked in sort order)
        above_team = None
        above_value = None
        above_zscore = None
        if my_pos > 0:
            candidate = sorted_teams[my_pos - 1]
            above_team = candidate["team_name"]
            above_value = candidate[key]
            above_zscore = team_zscores.get(above_team, {}).get(key)

        # Find nearest team below (next worse-ranked in sort order)
        below_team = None
        below_value = None
        below_zscore = None
        if my_pos < len(sorted_teams) - 1:
            candidate = sorted_teams[my_pos + 1]
            below_team = candidate["team_name"]
            below_value = candidate[key]
            below_zscore = team_zscores.get(below_team, {}).get(key)

        chart_rows.append({
            "category": cat["name"],
            "display": cat["display"],
            "key": key,
            "higher_is_better": hib,
            "is_percentage": pct_lookup.get(key, False),
            # Per-game mode data
            "my_value": my_value,
            "above_team": above_team,
            "above_value": above_value,
            "below_team": below_team,
            "below_value": below_value,
            "league_min": league_min,
            "league_max": league_max,
            # Z-score mode data
            "my_zscore": my_zscore,
            "above_zscore": above_zscore,
            "below_zscore": below_zscore,
            "z_min": z_min,
            "z_max": z_max,
        })

    return chart_rows


def _assign_tags(cat_analyses: List[Dict[str, Any]]) -> None:
    """
    Assign TARGET and DEFEND tags in-place.

    TARGET and DEFEND are independent — a category can be both.

    TARGET: top N_TARGETS categories by target_score (highest first).
            Only categories where the team is NOT already in 1st place
            (z_gap_up is not None) are eligible.
    DEFEND: categories with lowest z_gap_down (smallest buffer, most vulnerable).
            Any category with a z_gap_down is eligible, regardless of TARGET status.

    The legacy ``tag`` field is set to "TARGET" if only target, "DEFEND" if
    only defend, or "TARGET" if both (for backward compatibility with row
    highlighting). Use ``is_target`` / ``is_defend`` for precise checks.
    """
    # TARGET: highest target_score among categories that can still be improved
    scorable = [c for c in cat_analyses if c["target_score"] is not None and c["z_gap_up"] is not None]
    scorable.sort(key=lambda c: (-c["target_score"], c["category"]))

    for c in scorable[:N_TARGETS]:
        c["is_target"] = True
        c["tag"] = "TARGET"

    # DEFEND: lowest z_gap_down — independent of TARGET status
    defendable = [
        c for c in cat_analyses
        if c["z_gap_down"] is not None
    ]
    defendable.sort(key=lambda c: (c["z_gap_down"], c["category"]))

    for c in defendable[:N_DEFEND]:
        c["is_defend"] = True
        if c["tag"] is None:
            c["tag"] = "DEFEND"
