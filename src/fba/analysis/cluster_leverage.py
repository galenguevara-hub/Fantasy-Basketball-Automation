#!/usr/bin/env python3
"""
Cluster Leverage Analysis — Layer 2: Multi-Point Density / Cluster Potential.

For each team and category, measures how many roto-point jumps are within a
fixed effort threshold (T = 0.75 σ by default), signalling whether a modest
improvement (or decline) can swing multiple standings positions at once.

Scoring versions:
  v1 (legacy)  — count-based: score = reachable_tiers / T
  v2 (active)  — distance-weighted: weight(z) = 1 - z/T, score = Σweight / T

All computations use the same per-game normalised stats as Layer 1.
No web dependencies — pure data logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fba.category_config import CategoryConfig, DEFAULT_8CAT_CONFIG, get_analysis_keys
from fba.analysis.category_targets import CATEGORIES, compute_category_sigma

# Default effort threshold in z-score units.
T_DEFAULT: float = 0.75

# Tag counts mirror Layer 1 conventions.
N_CLUSTER_TARGETS: int = 3
N_CLUSTER_DEFEND: int = 3

# Scoring version: "v2" (distance-weighted) or "v1" (count-based legacy).
SCORING_VERSION: str = "v2"


def _weighted_score(z_distances: List[float], T: float) -> float:
    """Distance-weighted score: closer tiers contribute more. weight(z) = 1 - z/T."""
    return sum(1 - (z / T) for z in z_distances) / T


def _safe_mean(values: List[float]) -> Optional[float]:
    """Return the arithmetic mean, or None if the list is empty."""
    return sum(values) / len(values) if values else None


def compute_tiers(
    values_by_team: Dict[str, Optional[float]],
    higher_is_better: bool = True,
) -> List[float]:
    """
    Build an ordered list of distinct tier values from a team-value mapping.

    Returns distinct non-None values sorted best-first.
    For higher-is-better: descending (highest first).
    For lower-is-better: ascending (lowest first).

    Args:
        values_by_team: Dict mapping team_name -> category value (or None).
        higher_is_better: Sort direction.

    Returns:
        Sorted list of distinct non-None values, best first.
    """
    distinct = sorted(
        {v for v in values_by_team.values() if v is not None},
        reverse=higher_is_better,
    )
    return distinct


def compute_cluster_metrics(
    rows: List[Dict[str, Any]],
    T: float = T_DEFAULT,
    category_config: Optional[List[CategoryConfig]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute cluster leverage metrics for every team across all 8 categories.

    Args:
        rows: List of per-game row dicts (from normalize.build_per_game_rows).
        T:    Effort threshold in z units (default 0.75).

    Returns:
        Dict keyed by team_name -> {category_name -> metrics_dict}.

        Each metrics_dict contains:
            sigma              : population std dev for this category
            tier_idx           : 0-indexed tier position (0 = best tier)
            n_tiers            : total number of distinct tiers
            z_to_gain_1/2/3    : z required to jump 1/2/3 tiers above
            z_to_lose_1/2/3    : z required to fall 1/2/3 tiers below
            points_up_within_T : count of tiers above within T*sigma effort
            points_down_within_T: count of tiers below within T*sigma buffer
            cluster_up_score_v1: legacy count-based: points_up / T
            cluster_down_risk_v1: legacy count-based: points_down / T
            cluster_up_score_v2: distance-weighted: Σ(1 - z/T) / T
            cluster_down_risk_v2: distance-weighted: Σ(1 - z/T) / T
            z_up_max/mean      : max/mean of reachable upside z-distances
            z_down_max/mean    : max/mean of reachable downside z-distances
            cluster_up_score   : active score (v1 or v2 per SCORING_VERSION)
            cluster_down_risk  : active score (v1 or v2 per SCORING_VERSION)
            T                  : the threshold used

        All fields are None when sigma is None or the team has no value for
        this category.
    """
    if not rows:
        return {}

    cats = get_analysis_keys(category_config) if category_config else CATEGORIES
    sigmas = compute_category_sigma(rows, category_config)

    result: Dict[str, Dict[str, Any]] = {}

    for cat in cats:
        key = cat["key"]
        cat_name = cat["name"]
        hib = cat.get("higher_is_better", True)
        sigma = sigmas.get(key)

        # Build tier structure for this category.
        values_by_team: Dict[str, Optional[float]] = {
            r["team_name"]: r.get(key) for r in rows
        }
        tier_values = compute_tiers(values_by_team, hib)
        value_to_tier_idx: Dict[float, int] = {
            v: i for i, v in enumerate(tier_values)
        }
        n_tiers = len(tier_values)

        for row in rows:
            team_name = row["team_name"]
            if team_name not in result:
                result[team_name] = {}

            x_i = row.get(key)

            # No value or zero-variance sigma → all metrics undefined.
            if x_i is None or sigma is None:
                result[team_name][cat_name] = _none_cluster_entry()
                continue

            tier_idx = value_to_tier_idx[x_i]

            # z required to reach tier k positions above (None if impossible).
            # Tiers are sorted best-first, so gain = moving toward index 0.
            # z = absolute distance / sigma.
            def _z_gain(k: int) -> Optional[float]:
                target = tier_idx - k
                if target < 0:
                    return None
                return abs(tier_values[target] - x_i) / sigma  # type: ignore[operator]

            z_to_gain_1 = _z_gain(1)
            z_to_gain_2 = _z_gain(2)
            z_to_gain_3 = _z_gain(3)

            # z required to fall k tiers below (None if already at bottom).
            def _z_lose(k: int) -> Optional[float]:
                target = tier_idx + k
                if target >= n_tiers:
                    return None
                return abs(x_i - tier_values[target]) / sigma  # type: ignore[operator]

            z_to_lose_1 = _z_lose(1)
            z_to_lose_2 = _z_lose(2)
            z_to_lose_3 = _z_lose(3)

            # Collect reachable z-distances and count tiers within threshold.
            reachable_up = [
                abs(tier_values[j] - x_i) / sigma  # type: ignore[operator]
                for j in range(tier_idx)
                if abs(tier_values[j] - x_i) / sigma <= T  # type: ignore[operator]
            ]
            reachable_down = [
                abs(x_i - tier_values[j]) / sigma  # type: ignore[operator]
                for j in range(tier_idx + 1, n_tiers)
                if abs(x_i - tier_values[j]) / sigma <= T  # type: ignore[operator]
            ]

            points_up = len(reachable_up)
            points_down = len(reachable_down)

            # v1 legacy scoring (count-based, retained for rollback)
            up_v1 = points_up / T
            down_v1 = points_down / T

            # v2 distance-weighted scoring
            up_v2 = _weighted_score(reachable_up, T) if reachable_up else 0.0
            down_v2 = _weighted_score(reachable_down, T) if reachable_down else 0.0

            result[team_name][cat_name] = {
                "sigma": sigma,
                "tier_idx": tier_idx,
                "n_tiers": n_tiers,
                "z_to_gain_1": z_to_gain_1,
                "z_to_gain_2": z_to_gain_2,
                "z_to_gain_3": z_to_gain_3,
                "z_to_lose_1": z_to_lose_1,
                "z_to_lose_2": z_to_lose_2,
                "z_to_lose_3": z_to_lose_3,
                "points_up_within_T": points_up,
                "points_down_within_T": points_down,
                # v1 legacy scoring (count-based)
                "cluster_up_score_v1": up_v1,
                "cluster_down_risk_v1": down_v1,
                # v2 distance-weighted scoring
                "cluster_up_score_v2": up_v2,
                "cluster_down_risk_v2": down_v2,
                # Diagnostics
                "z_up_max": max(reachable_up) if reachable_up else None,
                "z_up_mean": _safe_mean(reachable_up),
                "z_down_max": max(reachable_down) if reachable_down else None,
                "z_down_mean": _safe_mean(reachable_down),
                # Active scores — used by tagging, sorting, and UI
                "cluster_up_score": up_v2 if SCORING_VERSION == "v2" else up_v1,
                "cluster_down_risk": down_v2 if SCORING_VERSION == "v2" else down_v1,
                "T": T,
                "tag": None,
                "is_target": False,
                "is_defend": False,
            }

    # Assign TARGET / DEFEND tags for each team after all categories are scored.
    for team_metrics in result.values():
        _assign_cluster_tags(team_metrics)

    return result


def _none_cluster_entry() -> Dict[str, Any]:
    """Return a cluster entry with all computed fields set to None."""
    return {
        "sigma": None,
        "tier_idx": None,
        "n_tiers": None,
        "z_to_gain_1": None,
        "z_to_gain_2": None,
        "z_to_gain_3": None,
        "z_to_lose_1": None,
        "z_to_lose_2": None,
        "z_to_lose_3": None,
        "points_up_within_T": None,
        "points_down_within_T": None,
        "cluster_up_score_v1": None,
        "cluster_down_risk_v1": None,
        "cluster_up_score_v2": None,
        "cluster_down_risk_v2": None,
        "z_up_max": None,
        "z_up_mean": None,
        "z_down_max": None,
        "z_down_mean": None,
        "cluster_up_score": None,
        "cluster_down_risk": None,
        "T": None,
        "tag": None,
        "is_target": False,
        "is_defend": False,
    }


def _assign_cluster_tags(team_metrics: Dict[str, Any]) -> None:
    """
    Assign TARGET / DEFEND tags in-place for one team's cluster metrics dict.

    TARGET and DEFEND are independent — a category can be both.

    TARGET: top N_CLUSTER_TARGETS categories by cluster_up_score (must be > 0).
    DEFEND: top N_CLUSTER_DEFEND categories by cluster_down_risk (must be > 0).

    Tie-break within each group: higher score first, then category name ascending.
    """
    # TARGET — highest cluster upside.
    up_candidates = [
        (cat_name, m) for cat_name, m in team_metrics.items()
        if m.get("cluster_up_score") is not None and m["cluster_up_score"] > 0
    ]
    up_candidates.sort(key=lambda x: (-x[1]["cluster_up_score"], x[0]))

    for cat_name, m in up_candidates[:N_CLUSTER_TARGETS]:
        m["tag"] = "TARGET"
        m["is_target"] = True

    # DEFEND — highest cluster fragility, independent of TARGET.
    down_candidates = [
        (cat_name, m) for cat_name, m in team_metrics.items()
        if m.get("cluster_down_risk") is not None
        and m["cluster_down_risk"] > 0
    ]
    down_candidates.sort(key=lambda x: (-x[1]["cluster_down_risk"], x[0]))

    for cat_name, m in down_candidates[:N_CLUSTER_DEFEND]:
        m["is_defend"] = True
        if m["tag"] is None:
            m["tag"] = "DEFEND"
