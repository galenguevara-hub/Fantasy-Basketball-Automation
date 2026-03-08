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


# The 8 roto categories and the per-game row keys they correspond to.
# Order matches the spec.
CATEGORIES: list[dict[str, str]] = [
    {"name": "FG%",   "key": "FG%",   "display": "FG%"},
    {"name": "FT%",   "key": "FT%",   "display": "FT%"},
    {"name": "3PM/G", "key": "3PM_pg", "display": "3PM/G"},
    {"name": "PTS/G", "key": "PTS_pg", "display": "PTS/G"},
    {"name": "REB/G", "key": "REB_pg", "display": "REB/G"},
    {"name": "AST/G", "key": "AST_pg", "display": "AST/G"},
    {"name": "STL/G", "key": "ST_pg",  "display": "STL/G"},
    {"name": "BLK/G", "key": "BLK_pg", "display": "BLK/G"},
]

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
) -> Dict[str, Optional[float]]:
    """
    Compute population std dev (ddof=0) for each category across teams.

    Args:
        rows: List of per-game row dicts (from normalize.build_per_game_rows).

    Returns:
        Dict mapping category key -> sigma (float), or None if non-actionable
        (all values missing or zero variance).
    """
    sigmas: Dict[str, Optional[float]] = {}

    for cat in CATEGORIES:
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
) -> List[Dict[str, Any]]:
    """
    Sort teams by a category value, descending (best first).
    Teams with None values are excluded.
    Tie-break by team_name ascending for stability.
    """
    valid = [r for r in rows if r.get(key) is not None]
    return sorted(valid, key=lambda r: (-r[key], r["team_name"]))


def compute_gaps_and_scores(
    rows: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compute gap-to-gain, buffer-to-lose, target score, and recommendations
    for every team across all 8 categories.

    Args:
        rows: List of per-game row dicts.

    Returns:
        Dict keyed by team_name, each value is a list of category analysis dicts:
        [
            {
                "category": "FG%",
                "display": "FG%",
                "value": 0.476,
                "rank": 3,
                "next_better_team": "Team X",
                "next_better_value": 0.482,
                "gap_up": 0.006,
                "z_gap_up": 0.45,
                "next_worse_team": "Team Y",
                "next_worse_value": 0.470,
                "gap_down": 0.006,
                "z_gap_down": 0.45,
                "target_score": 2.33,
                "tag": "TARGET",
            },
            ...
        ]
    """
    if not rows:
        return {}

    sigmas = compute_category_sigma(rows)

    # Pre-compute sorted order and ranks per category.
    sorted_by_cat: Dict[str, List[Dict[str, Any]]] = {}
    ranks_by_cat: Dict[str, Dict[str, int]] = {}

    for cat in CATEGORIES:
        key = cat["key"]
        sorted_teams = _sorted_teams_for_category(rows, key)
        sorted_by_cat[key] = sorted_teams

        # Assign ranks: best = N (number of teams with values), worst = 1.
        # Teams with None get no rank entry (handled as None later).
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

        for cat in CATEGORIES:
            key = cat["key"]
            value = row.get(key)
            sigma = sigmas.get(key)
            sorted_teams = sorted_by_cat[key]
            ranks = ranks_by_cat[key]

            rank = ranks.get(team_name)

            # If this team has no value for this category, skip with Nones.
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

            # --- Gap up (effort): find nearest team with strictly better value ---
            next_better_team = None
            next_better_value = None
            gap_up = None
            z_gap_up = None

            # Look backwards in sorted list (positions 0..team_pos-1) for
            # strictly better value.
            for j in range(team_pos - 1, -1, -1):
                candidate = sorted_teams[j]
                if candidate[key] > value:
                    next_better_team = candidate["team_name"]
                    next_better_value = candidate[key]
                    gap_up = candidate[key] - value
                    break

            if gap_up is not None and sigma is not None and sigma > 0:
                z_gap_up = gap_up / sigma

            # --- Gap down (risk): find nearest team with strictly worse value ---
            next_worse_team = None
            next_worse_value = None
            gap_down = None
            z_gap_down = None

            for j in range(team_pos + 1, len(sorted_teams)):
                candidate = sorted_teams[j]
                if candidate[key] < value:
                    next_worse_team = candidate["team_name"]
                    next_worse_value = candidate[key]
                    gap_down = value - candidate[key]
                    break

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
                "tag": None,  # filled in below
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
