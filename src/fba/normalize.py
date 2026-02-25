#!/usr/bin/env python3
"""
Per-game normalization and ranking for Fantasy Basketball standings.

Transforms raw team stats into:
- Per-game averages for counting stats
- Rankings by category
"""

from typing import Any, Dict, List, Optional, Tuple


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


def calculate_per_game_stats(team: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    Calculate per-game stats for a team.

    Args:
        team: Team dict with 'stats' key containing raw stat values.

    Returns:
        Dict with per-game values:
        {
            "PTS_pg": float or None,
            "REB_pg": float or None,
            "AST_pg": float or None,
            "ST_pg": float or None,
            "BLK_pg": float or None,
            "3PM_pg": float or None,
        }
        If GP is 0 or missing, all values are None.
    """
    stats = team.get("stats", {})
    gp = parse_stat_value(stats.get("GP"))

    # If no GP or GP is 0, return None for all per-game stats
    if gp is None or gp == 0:
        return {
            "PTS_pg": None,
            "REB_pg": None,
            "AST_pg": None,
            "ST_pg": None,
            "BLK_pg": None,
            "3PM_pg": None,
        }

    # Parse counting stats
    pts = parse_stat_value(stats.get("PTS"))
    reb = parse_stat_value(stats.get("REB"))
    ast = parse_stat_value(stats.get("AST"))
    st = parse_stat_value(stats.get("ST"))
    blk = parse_stat_value(stats.get("BLK"))
    three_pm = parse_stat_value(stats.get("3PTM"))

    return {
        "PTS_pg": pts / gp if pts is not None else None,
        "REB_pg": reb / gp if reb is not None else None,
        "AST_pg": ast / gp if ast is not None else None,
        "ST_pg": st / gp if st is not None else None,
        "BLK_pg": blk / gp if blk is not None else None,
        "3PM_pg": three_pm / gp if three_pm is not None else None,
    }


def build_per_game_rows(
    teams: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build per-game averages rows from raw team data.

    Args:
        teams: List of team dicts with stats.

    Returns:
        List of dicts, one per team, with team info + per-game stats + percentages.
    """
    rows = []

    for team in teams:
        stats = team.get("stats", {})
        gp = parse_stat_value(stats.get("GP"))

        pg_stats = calculate_per_game_stats(team)

        # Get percentage stats (as-is, no division)
        fg_pct = parse_stat_value(stats.get("FG%"))
        ft_pct = parse_stat_value(stats.get("FT%"))

        row = {
            "team_name": team.get("team_name", ""),
            "rank": team.get("rank"),
            "total_points": team.get("total_points"),
            "GP": int(gp) if gp is not None else None,
            "PTS_pg": pg_stats["PTS_pg"],
            "REB_pg": pg_stats["REB_pg"],
            "AST_pg": pg_stats["AST_pg"],
            "ST_pg": pg_stats["ST_pg"],
            "BLK_pg": pg_stats["BLK_pg"],
            "3PM_pg": pg_stats["3PM_pg"],
            "FG%": fg_pct,
            "FT%": ft_pct,
        }

        rows.append(row)

    return rows


def rank_teams_by_category(
    per_game_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Rank teams by each category (higher is better for all).

    Ranking logic:
    - Scale: N = best (highest value), 1 = worst (lowest value / missing)
    - Tie-break by team_name (ascending) for determinism
    - Missing/None values receive rank 1 (worst)

    Args:
        per_game_rows: List of per-game row dicts.

    Returns:
        List of dicts, one per team, with team name + rank for each category.
    """
    categories = [
        "PTS_pg",
        "REB_pg",
        "AST_pg",
        "ST_pg",
        "BLK_pg",
        "3PM_pg",
        "FG%",
        "FT%",
    ]

    n_teams = len(per_game_rows)

    # Build ranking for each category
    rankings = {}  # {team_name: {category: rank}}

    for category in categories:
        # Extract values with team names
        values_with_teams = []
        for row in per_game_rows:
            value = row.get(category)
            team_name = row.get("team_name")
            values_with_teams.append((team_name, value))

        # Sort best-first: None values sink to the end (will receive rank 1)
        def sort_key(item):
            team_name, value = item
            if value is None:
                return (1, 0, team_name)  # None sorts last → gets rank 1
            return (0, -value, team_name)  # Higher value sorts first → gets rank N

        sorted_teams = sorted(values_with_teams, key=sort_key)

        # Assign inverted ranks: position 1 (best) → rank n_teams, position N → rank 1
        for position, (team_name, _) in enumerate(sorted_teams, start=1):
            if team_name not in rankings:
                rankings[team_name] = {}
            rankings[team_name][category] = n_teams + 1 - position

    # Build output rows
    ranking_rows = []
    for row in per_game_rows:
        team_name = row.get("team_name")
        rank_data = rankings.get(team_name, {})

        cat_ranks = [
            rank_data.get("PTS_pg"),
            rank_data.get("REB_pg"),
            rank_data.get("AST_pg"),
            rank_data.get("ST_pg"),
            rank_data.get("BLK_pg"),
            rank_data.get("3PM_pg"),
            rank_data.get("FG%"),
            rank_data.get("FT%"),
        ]
        numeric_ranks = [r for r in cat_ranks if r is not None]
        rank_total = sum(numeric_ranks) if numeric_ranks else None

        ranking_row = {
            "team_name": team_name,
            "rank": row.get("rank"),
            "GP": row.get("GP"),
            "total_points": row.get("total_points"),
            "PTS_Rank": rank_data.get("PTS_pg"),
            "REB_Rank": rank_data.get("REB_pg"),
            "AST_Rank": rank_data.get("AST_pg"),
            "ST_Rank": rank_data.get("ST_pg"),
            "BLK_Rank": rank_data.get("BLK_pg"),
            "3PM_Rank": rank_data.get("3PM_pg"),
            "FG%_Rank": rank_data.get("FG%"),
            "FT%_Rank": rank_data.get("FT%"),
            "rank_total": rank_total,
            "points_delta": (rank_total - row.get("total_points"))
            if rank_total is not None and row.get("total_points") is not None
            else None,
        }

        ranking_rows.append(ranking_row)

    return ranking_rows


def normalize_standings(teams: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main entry point: normalize standings and generate per-game + ranking tables.

    Args:
        teams: Raw team list from scraper.

    Returns:
        Dict with:
        {
            "per_game_rows": [list of per-game dicts],
            "ranking_rows": [list of ranking dicts],
        }
    """
    per_game_rows = build_per_game_rows(teams)
    ranking_rows = rank_teams_by_category(per_game_rows)

    return {
        "per_game_rows": per_game_rows,
        "ranking_rows": ranking_rows,
    }
