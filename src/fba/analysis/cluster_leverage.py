#!/usr/bin/env python3
"""
Cluster Leverage Analysis — Layer 2: Multi-Point Density / Cluster Potential.

For each team and category, measures how many roto-point jumps are within a
fixed effort threshold (T = 0.75 σ by default), signalling whether a modest
improvement (or decline) can swing multiple standings positions at once.

All computations use the same per-game normalised stats as Layer 1.
No web dependencies — pure data logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fba.analysis.category_targets import CATEGORIES, compute_category_sigma

# Default effort threshold in z-score units.
T_DEFAULT: float = 0.75

# Tag counts mirror Layer 1 conventions.
N_CLUSTER_TARGETS: int = 3
N_CLUSTER_DEFEND: int = 2


def compute_tiers(values_by_team: Dict[str, Optional[float]]) -> List[float]:
    """
    Build an ordered list of distinct tier values from a team-value mapping.

    Returns distinct non-None values sorted descending (best first).
    Two teams with the same value occupy the same tier; crossing a tier
    boundary represents exactly one roto-point gain or loss.

    Args:
        values_by_team: Dict mapping team_name -> category value (or None).

    Returns:
        Sorted list of distinct non-None values, highest first.
    """
    distinct = sorted(
        {v for v in values_by_team.values() if v is not None},
        reverse=True,
    )
    return distinct


def compute_cluster_metrics(
    rows: List[Dict[str, Any]],
    T: float = T_DEFAULT,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute cluster leverage metrics for every team across all 8 categories.

    Args:
        rows: List of per-game row dicts (from normalize.build_per_game_rows).
        T:    Effort threshold in z units (default 0.75).

    Returns:
        Dict keyed by team_name -> {category_name -> metrics_dict}.

        Each metrics_dict contains:
            sigma              : population std dev for this category (None if
                                 sigma == 0 or fewer than 2 valid values)
            tier_idx           : 0-indexed tier position (0 = best tier)
            n_tiers            : total number of distinct tiers
            z_to_gain_1        : z required to reach the next tier above
            z_to_gain_2        : z required to jump 2 tiers above (or None)
            z_to_gain_3        : z required to jump 3 tiers above (or None)
            points_up_within_T : number of tiers above within T*sigma effort
            cluster_up_score   : points_up_within_T / T
            points_down_within_T: number of tiers below within T*sigma buffer
            cluster_down_risk  : points_down_within_T / T
            T                  : the threshold used

        All fields are None when sigma is None or the team has no value for
        this category.
    """
    if not rows:
        return {}

    sigmas = compute_category_sigma(rows)

    result: Dict[str, Dict[str, Any]] = {}

    for cat in CATEGORIES:
        key = cat["key"]
        cat_name = cat["name"]
        sigma = sigmas.get(key)

        # Build tier structure for this category.
        values_by_team: Dict[str, Optional[float]] = {
            r["team_name"]: r.get(key) for r in rows
        }
        tier_values = compute_tiers(values_by_team)
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
            def _z_gain(k: int) -> Optional[float]:
                target = tier_idx - k
                if target < 0:
                    return None
                return (tier_values[target] - x_i) / sigma  # type: ignore[operator]

            z_to_gain_1 = _z_gain(1)
            z_to_gain_2 = _z_gain(2)
            z_to_gain_3 = _z_gain(3)

            # z required to fall k tiers below (None if already at bottom).
            def _z_lose(k: int) -> Optional[float]:
                target = tier_idx + k
                if target >= n_tiers:
                    return None
                return (x_i - tier_values[target]) / sigma  # type: ignore[operator]

            z_to_lose_1 = _z_lose(1)
            z_to_lose_2 = _z_lose(2)
            z_to_lose_3 = _z_lose(3)

            # Tiers above whose threshold is within T*sigma effort.
            points_up = sum(
                1
                for j in range(tier_idx)          # indices 0 .. tier_idx-1
                if (tier_values[j] - x_i) / sigma <= T  # type: ignore[operator]
            )

            # Tiers below whose threshold is within T*sigma buffer.
            points_down = sum(
                1
                for j in range(tier_idx + 1, n_tiers)
                if (x_i - tier_values[j]) / sigma <= T  # type: ignore[operator]
            )

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
                "cluster_up_score": points_up / T,
                "points_down_within_T": points_down,
                "cluster_down_risk": points_down / T,
                "T": T,
                "tag": None,
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
        "cluster_up_score": None,
        "points_down_within_T": None,
        "cluster_down_risk": None,
        "T": None,
        "tag": None,
    }


def _assign_cluster_tags(team_metrics: Dict[str, Any]) -> None:
    """
    Assign TARGET / DEFEND tags in-place for one team's cluster metrics dict.

    TARGET: top N_CLUSTER_TARGETS categories by cluster_up_score (must be > 0).
    DEFEND: top N_CLUSTER_DEFEND categories by cluster_down_risk (must be > 0),
            only among categories not already tagged TARGET.

    Tie-break within each group: higher score first, then category name ascending.
    """
    # TARGET — highest cluster upside.
    up_candidates = [
        (cat_name, m) for cat_name, m in team_metrics.items()
        if m.get("cluster_up_score") is not None and m["cluster_up_score"] > 0
    ]
    up_candidates.sort(key=lambda x: (-x[1]["cluster_up_score"], x[0]))

    target_cats: set = set()
    for cat_name, m in up_candidates[:N_CLUSTER_TARGETS]:
        m["tag"] = "TARGET"
        target_cats.add(cat_name)

    # DEFEND — highest cluster fragility, excluding already-tagged categories.
    down_candidates = [
        (cat_name, m) for cat_name, m in team_metrics.items()
        if cat_name not in target_cats
        and m.get("cluster_down_risk") is not None
        and m["cluster_down_risk"] > 0
    ]
    down_candidates.sort(key=lambda x: (-x[1]["cluster_down_risk"], x[0]))

    for cat_name, m in down_candidates[:N_CLUSTER_DEFEND]:
        m["tag"] = "DEFEND"
