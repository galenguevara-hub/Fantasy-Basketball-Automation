"""
Games Played Pace Analysis

Computes per-team GP pace metrics for the current season:
  - avg_gp_per_day_so_far  : GP earned to date / elapsed days (inclusive)
  - avg_gp_per_day_needed  : (total_games − GP) / remaining days (inclusive)
  - net_rate_delta         : avg_needed - avg_so_far
                             positive → behind pace (need to speed up)
                             negative → ahead of pace (can slow down)

Also provides projected end-of-season counting totals and roto rankings
based on current GP pace extrapolated through the season end.
"""

from datetime import date
from typing import Optional

from fba.normalize import parse_stat_value


def compute_games_played_metrics(
    teams: list[dict],
    start_date: date,
    end_date: date,
    today_date: date,
    total_games: int = 816,
) -> tuple[list[dict], bool]:
    """
    Compute GP pace metrics for each team.

    Parameters
    ----------
    teams       : list of team dicts from standings.json (must contain stats["GP"])
    start_date  : first day of the season (inclusive)
    end_date    : last day of the season (inclusive)
    today_date  : the reference "today" for elapsed / remaining calculation
    total_games : total season games cap per team (default 816)

    Returns
    -------
    (rows, date_valid) where:
      rows       : list of metric dicts, one per team
      date_valid : False if today is outside [start_date, end_date];
                   callers should show an error banner when False
    """
    elapsed_days = (today_date - start_date).days + 1      # inclusive
    remaining_days = (end_date - today_date).days + 1      # inclusive

    date_valid = elapsed_days >= 1 and remaining_days >= 1

    rows = []
    for team in teams:
        gp_raw = team.get("stats", {}).get("GP")
        try:
            gp = int(gp_raw) if gp_raw is not None else None
        except (TypeError, ValueError):
            gp = None

        if gp is not None and date_valid:
            games_remaining = total_games - gp
            avg_so_far = gp / elapsed_days
            avg_needed = games_remaining / remaining_days
            net_rate_delta = avg_needed - avg_so_far
        else:
            games_remaining = None
            avg_so_far = None
            avg_needed = None
            net_rate_delta = None

        rows.append({
            "team_name": team.get("team_name", ""),
            "rank": team.get("rank"),
            "gp": gp,
            "games_remaining": games_remaining,
            "elapsed_days": elapsed_days if date_valid else None,
            "remaining_days": remaining_days if date_valid else None,
            "avg_gp_per_day_so_far": avg_so_far,
            "avg_gp_per_day_needed": avg_needed,
            "net_rate_delta": net_rate_delta,
        })

    return rows, date_valid


# ---------------------------------------------------------------------------
# Counting-stat categories used for end-of-season projections.
# Keys match the raw stat keys from yahoo_api.py's STAT_ID_MAP.
# ---------------------------------------------------------------------------
COUNTING_CATEGORIES = [
    {"key": "3PTM", "display": "3PTM"},
    {"key": "PTS",  "display": "PTS"},
    {"key": "REB",  "display": "REB"},
    {"key": "AST",  "display": "AST"},
    {"key": "ST",   "display": "STL"},
    {"key": "BLK",  "display": "BLK"},
]


def compute_projected_totals(
    teams: list[dict],
    start_date: date,
    end_date: date,
    today_date: date,
    total_games: int = 816,
) -> list[dict]:
    """Project end-of-season counting-stat totals based on current GP pace.

    For each team:
      projected_gp = min(gp_per_day * total_season_days, total_games)
      projected_<stat> = (stat / gp) * projected_gp

    Parameters
    ----------
    teams       : raw team dicts (with stats and roto_points)
    start_date  : season start (inclusive)
    end_date    : season end (inclusive)
    today_date  : current date reference
    total_games : season games cap per team

    Returns
    -------
    List of dicts, one per team, with projected_gp and projected counting totals.
    Returns empty list if date is invalid.
    """
    elapsed_days = (today_date - start_date).days + 1
    total_season_days = (end_date - start_date).days + 1

    if elapsed_days < 1 or (end_date - today_date).days + 1 < 1:
        return []

    rows: list[dict] = []
    for team in teams:
        stats = team.get("stats", {})
        gp = parse_stat_value(stats.get("GP"))
        gp = int(gp) if gp is not None else None

        row: dict = {
            "team_name": team.get("team_name", ""),
            "rank": team.get("rank"),
            "projected_gp": None,
        }
        for cat in COUNTING_CATEGORIES:
            row[f"projected_{cat['key']}"] = None

        if gp is None or gp == 0 or elapsed_days == 0:
            rows.append(row)
            continue

        gp_per_day = gp / elapsed_days
        projected_gp = min(gp_per_day * total_season_days, total_games)
        row["projected_gp"] = round(projected_gp)

        for cat in COUNTING_CATEGORIES:
            raw_val = parse_stat_value(stats.get(cat["key"]))
            if raw_val is not None:
                per_game = raw_val / gp
                row[f"projected_{cat['key']}"] = round(per_game * projected_gp)
            # else stays None

        rows.append(row)

    return rows


def compute_projected_roto_ranks(
    projected_rows: list[dict],
    teams: list[dict],
) -> list[dict]:
    """Rank teams by projected counting totals, adding FG%/FT% base ranks from Yahoo.

    Ranking logic matches normalize.rank_teams_by_category:
      - Higher value = higher rank (N = best, 1 = worst)
      - None values get rank 1 (worst)
      - Tie-break by team_name ascending for determinism

    FG% and FT% ranks are carried forward from Yahoo's roto_points data
    (which uses tie-averaged ranks) rather than being re-projected.

    Parameters
    ----------
    projected_rows : output of compute_projected_totals()
    teams          : raw team dicts (with roto_points from Yahoo)

    Returns
    -------
    List of dicts with per-category ranks and projected_total score.
    """
    if not projected_rows:
        return []

    n_teams = len(projected_rows)

    # Build Yahoo FG%/FT% rank lookup from roto_points
    yahoo_ranks: dict[str, dict[str, Optional[float]]] = {}
    for team in teams:
        name = team.get("team_name", "")
        rp = team.get("roto_points", {})
        yahoo_ranks[name] = {
            "FG%": rp.get("FG%"),
            "FT%": rp.get("FT%"),
        }

    # Rank each counting category
    counting_keys = [f"projected_{cat['key']}" for cat in COUNTING_CATEGORIES]
    rankings: dict[str, dict[str, int]] = {r["team_name"]: {} for r in projected_rows}

    for proj_key in counting_keys:
        entries = []
        for r in projected_rows:
            val = r.get(proj_key)
            entries.append((r["team_name"], val))

        # Sort: None sinks to end (rank 1), higher value sorts first (rank N)
        def sort_key(item, _proj_key=proj_key):
            name, val = item
            if val is None:
                return (1, 0, name)
            return (0, -val, name)

        entries.sort(key=sort_key)

        for position, (name, _) in enumerate(entries, start=1):
            rankings[name][proj_key] = n_teams + 1 - position

    # Build output rows
    result: list[dict] = []
    for r in projected_rows:
        name = r["team_name"]
        rank_data = rankings.get(name, {})
        yr = yahoo_ranks.get(name, {})

        row: dict = {
            "team_name": name,
            "rank": r.get("rank"),
            "projected_gp": r.get("projected_gp"),
        }

        # Counting-stat ranks (use display names as keys for the frontend)
        cat_rank_sum: list[float] = []
        for cat in COUNTING_CATEGORIES:
            proj_key = f"projected_{cat['key']}"
            rank_val = rank_data.get(proj_key)
            row[f"{cat['key']}_Rank"] = rank_val
            if rank_val is not None:
                cat_rank_sum.append(rank_val)

        # FG% and FT% from Yahoo base ranks
        fg_rank = yr.get("FG%")
        ft_rank = yr.get("FT%")
        row["FG%_Rank"] = fg_rank
        row["FT%_Rank"] = ft_rank
        if fg_rank is not None:
            cat_rank_sum.append(fg_rank)
        if ft_rank is not None:
            cat_rank_sum.append(ft_rank)

        row["projected_total"] = sum(cat_rank_sum) if cat_rank_sum else None

        result.append(row)

    return result
