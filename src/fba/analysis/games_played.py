"""
Games Played Pace Analysis

Computes per-team GP pace metrics for the current season:
  - avg_gp_per_day_so_far  : GP earned to date / elapsed days (inclusive)
  - avg_gp_per_day_needed  : (total_games − GP) / remaining days (inclusive)
  - net_rate_delta         : avg_needed - avg_so_far
                             positive → behind pace (need to speed up)
                             negative → ahead of pace (can slow down)
"""

from datetime import date


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
