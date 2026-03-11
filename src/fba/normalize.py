#!/usr/bin/env python3
"""
Per-game normalization and ranking for Fantasy Basketball standings.

Transforms raw team stats into:
- Per-game averages for counting stats
- Rankings by category

Supports dynamic category sets via CategoryConfig.
"""

from typing import Any, Dict, List, Optional, Tuple

from fba.category_config import (
    CategoryConfig,
    DEFAULT_8CAT_CONFIG,
    get_counting_configs,
)


def parse_stat_value(value: Any) -> Optional[float]:
    """
    Parse a stat value that may be a string with commas, int, float, or None.

    Args:
        value: Raw stat value (could be "1,256", 664, 0.476, None, "—", etc.)

    Returns:
        Parsed float, or None if invalid/missing.
    """
    if value is None or value == "—" or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        # Remove commas and try to convert
        cleaned = value.replace(",", "").strip()
        if not cleaned or cleaned == "—":
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def calculate_per_game_stats(
    team: Dict[str, Any],
    category_config: Optional[List[CategoryConfig]] = None,
) -> Dict[str, Optional[float]]:
    """
    Calculate per-game stats for a team.

    Args:
        team: Team dict with 'stats' key containing raw stat values.
        category_config: Optional dynamic config. Falls back to 8-cat default.

    Returns:
        Dict with per-game values for each counting category (e.g., "PTS_pg": float).
        If GP is 0 or missing, all values are None.
    """
    configs = category_config if category_config is not None else DEFAULT_8CAT_CONFIG
    counting = get_counting_configs(configs)

    stats = team.get("stats", {})
    gp = parse_stat_value(stats.get("GP"))

    result = {}

    if gp is None or gp == 0:
        for c in counting:
            result[c.per_game_key] = None
        return result

    for c in counting:
        raw = parse_stat_value(stats.get(c.key))
        result[c.per_game_key] = raw / gp if raw is not None else None

    return result


def build_per_game_rows(
    teams: List[Dict[str, Any]],
    category_config: Optional[List[CategoryConfig]] = None,
) -> List[Dict[str, Any]]:
    """
    Build per-game averages rows from raw team data.

    Args:
        teams: List of team dicts with stats.
        category_config: Optional dynamic config. Falls back to 8-cat default.

    Returns:
        List of dicts, one per team, with team info + per-game stats + percentages.
    """
    configs = category_config if category_config is not None else DEFAULT_8CAT_CONFIG

    rows = []

    for team in teams:
        stats = team.get("stats", {})
        gp = parse_stat_value(stats.get("GP"))

        pg_stats = calculate_per_game_stats(team, configs)

        row = {
            "team_name": team.get("team_name", ""),
            "rank": team.get("rank"),
            "total_points": team.get("total_points"),
            "GP": int(gp) if gp is not None else None,
        }

        # Add per-game counting stats
        row.update(pg_stats)

        # Add percentage stats (as-is, not per-game)
        for c in configs:
            if c.is_percentage:
                row[c.key] = parse_stat_value(stats.get(c.key))

        rows.append(row)

    return rows


def rank_teams_by_category(
    per_game_rows: List[Dict[str, Any]],
    category_config: Optional[List[CategoryConfig]] = None,
) -> List[Dict[str, Any]]:
    """
    Rank teams by each category, respecting directionality.

    Ranking logic:
    - Scale: N = best, 1 = worst (lowest value / missing for higher-is-better)
    - Tie-break by team_name (ascending) for determinism
    - Missing/None values receive rank 1 (worst)

    Args:
        per_game_rows: List of per-game row dicts.
        category_config: Optional dynamic config. Falls back to 8-cat default.

    Returns:
        List of dicts, one per team, with team name + rank for each category.
    """
    configs = category_config if category_config is not None else DEFAULT_8CAT_CONFIG

    # Build (data_key, rank_key, higher_is_better) tuples for each category
    cat_specs = []
    for c in configs:
        data_key = c.per_game_key if c.per_game_key else c.key
        cat_specs.append((data_key, c.rank_key, c.higher_is_better))

    n_teams = len(per_game_rows)

    # Build ranking for each category
    rankings: Dict[str, Dict[str, int]] = {}

    for data_key, rank_key, higher_is_better in cat_specs:
        values_with_teams = []
        for row in per_game_rows:
            value = row.get(data_key)
            team_name = row.get("team_name")
            values_with_teams.append((team_name, value))

        # Sort best-first: None values sink to the end (will receive rank 1)
        sign = -1 if higher_is_better else 1

        def sort_key(item, _sign=sign):
            team_name, value = item
            if value is None:
                return (1, 0, team_name)  # None sorts last → gets rank 1
            return (0, _sign * value, team_name)

        sorted_teams = sorted(values_with_teams, key=sort_key)

        # Assign inverted ranks: position 1 (best) → rank n_teams, position N → rank 1
        for position, (team_name, _) in enumerate(sorted_teams, start=1):
            if team_name not in rankings:
                rankings[team_name] = {}
            rankings[team_name][data_key] = n_teams + 1 - position

    # Build output rows
    ranking_rows = []
    for row in per_game_rows:
        team_name = row.get("team_name")
        rank_data = rankings.get(team_name, {})

        ranking_row: Dict[str, Any] = {
            "team_name": team_name,
            "rank": row.get("rank"),
            "GP": row.get("GP"),
            "total_points": row.get("total_points"),
        }

        # Add per-category rank columns and compute total
        numeric_ranks = []
        for data_key, rank_key, _ in cat_specs:
            rank_val = rank_data.get(data_key)
            ranking_row[rank_key] = rank_val
            if rank_val is not None:
                numeric_ranks.append(rank_val)

        rank_total = sum(numeric_ranks) if numeric_ranks else None
        ranking_row["rank_total"] = rank_total
        ranking_row["points_delta"] = (
            (rank_total - row.get("total_points"))
            if rank_total is not None and row.get("total_points") is not None
            else None
        )

        ranking_rows.append(ranking_row)

    return ranking_rows


def normalize_standings(
    teams: List[Dict[str, Any]],
    category_config: Optional[List[CategoryConfig]] = None,
) -> Dict[str, Any]:
    """
    Main entry point: normalize standings and generate per-game + ranking tables.

    Args:
        teams: Raw team list from scraper.
        category_config: Optional dynamic category config.

    Returns:
        Dict with:
        {
            "per_game_rows": [list of per-game dicts],
            "ranking_rows": [list of ranking dicts],
        }
    """
    per_game_rows = build_per_game_rows(teams, category_config)
    ranking_rows = rank_teams_by_category(per_game_rows, category_config)

    return {
        "per_game_rows": per_game_rows,
        "ranking_rows": ranking_rows,
    }
