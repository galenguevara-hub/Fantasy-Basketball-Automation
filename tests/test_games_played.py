"""
Tests for src/fba/analysis/games_played.py
"""

from datetime import date

import pytest

from fba.analysis.games_played import (
    compute_games_played_metrics,
    compute_projected_roto_ranks,
    compute_projected_totals,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_team(name: str, gp: int, rank: int = 1) -> dict:
    return {
        "team_name": name,
        "rank": rank,
        "stats": {"GP": gp},
    }


SEASON_START = date(2025, 10, 21)
SEASON_END = date(2026, 3, 22)


# ---------------------------------------------------------------------------
# Inclusive day counting
# ---------------------------------------------------------------------------

class TestDayCounting:
    def test_elapsed_days_is_inclusive(self):
        """Day 1 of the season should give elapsed_days=1."""
        teams = [make_team("Team A", 1)]
        today = SEASON_START  # first day
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        assert rows[0]["elapsed_days"] == 1

    def test_remaining_days_is_inclusive(self):
        """Last day of the season should give remaining_days=1."""
        teams = [make_team("Team A", 100)]
        today = SEASON_END  # last day
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        assert rows[0]["remaining_days"] == 1

    def test_elapsed_and_remaining_sum_to_season_length_plus_one(self):
        """elapsed + remaining = total season days + 1 (today counted in both)."""
        teams = [make_team("Team A", 50)]
        today = date(2025, 12, 1)
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        total_season_days = (SEASON_END - SEASON_START).days + 1
        assert rows[0]["elapsed_days"] + rows[0]["remaining_days"] == total_season_days + 1


# ---------------------------------------------------------------------------
# Metric calculations
# ---------------------------------------------------------------------------

class TestMetricCalculations:
    def test_avg_so_far(self):
        """avg_gp_per_day_so_far = gp / elapsed_days."""
        teams = [make_team("Team A", 30)]
        # elapsed = 30 days (day 1 through day 30 inclusive)
        today = date(2025, 10, 21) + __import__("datetime").timedelta(days=29)
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        assert rows[0]["elapsed_days"] == 30
        assert abs(rows[0]["avg_gp_per_day_so_far"] - 30 / 30) < 1e-9

    def test_avg_needed(self):
        """avg_gp_per_day_needed = (total_games - gp) / remaining_days."""
        teams = [make_team("Team A", 30)]
        today = date(2025, 10, 21) + __import__("datetime").timedelta(days=29)
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        expected_remaining = (SEASON_END - today).days + 1
        assert abs(rows[0]["avg_gp_per_day_needed"] - (816 - 30) / expected_remaining) < 1e-9

    def test_avg_needed_uses_total_games_param(self):
        """Custom total_games value is used in the avg_needed formula."""
        teams = [make_team("Team A", 40)]
        today = date(2025, 12, 1)
        rows, valid = compute_games_played_metrics(
            teams, SEASON_START, SEASON_END, today, total_games=100
        )
        assert valid is True
        expected_remaining = (SEASON_END - today).days + 1
        # games_remaining = 100 - 40 = 60
        assert abs(rows[0]["avg_gp_per_day_needed"] - 60 / expected_remaining) < 1e-9
        assert rows[0]["games_remaining"] == 60

    def test_net_rate_delta_positive_means_behind(self):
        """
        If avg_needed > avg_so_far the team is behind pace (needs more GP/day).
        A team with very few GP near the end of the season is clearly behind.
        """
        teams = [make_team("Team A", 10)]
        # Near end of season: only 12 days left, 148+ elapsed, 806 games still needed
        today = date(2026, 3, 10)
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        # avg_needed = (816-10)/12 ≈ 67.2, avg_so_far = 10/148 ≈ 0.07
        assert rows[0]["net_rate_delta"] > 0

    def test_net_rate_delta_negative_means_ahead(self):
        """
        If avg_needed < avg_so_far the team is ahead of pace.
        A team that has played many games early in the season is ahead.
        """
        teams = [make_team("Team A", 700)]
        today = date(2025, 10, 27)  # only 7 days elapsed
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        # avg_so_far = 700/7 = 100, avg_needed = (816-700)/147 ≈ 0.79 → delta < 0
        assert rows[0]["net_rate_delta"] < 0


# ---------------------------------------------------------------------------
# date_valid flag
# ---------------------------------------------------------------------------

class TestDateValid:
    def test_valid_on_first_day(self):
        teams = [make_team("Team A", 1)]
        _, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, SEASON_START)
        assert valid is True

    def test_valid_on_last_day(self):
        teams = [make_team("Team A", 100)]
        _, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, SEASON_END)
        assert valid is True

    def test_invalid_before_season(self):
        teams = [make_team("Team A", 0)]
        today = date(2025, 10, 13)  # one day before start
        _, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is False

    def test_invalid_after_season(self):
        teams = [make_team("Team A", 100)]
        today = date(2026, 3, 23)  # one day after end
        _, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is False

    def test_metrics_none_when_date_invalid(self):
        """All computed metrics should be None when date_valid is False."""
        teams = [make_team("Team A", 50)]
        today = date(2026, 4, 1)  # after season
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is False
        assert rows[0]["avg_gp_per_day_so_far"] is None
        assert rows[0]["avg_gp_per_day_needed"] is None
        assert rows[0]["net_rate_delta"] is None
        assert rows[0]["elapsed_days"] is None
        assert rows[0]["remaining_days"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_missing_gp_stat(self):
        """Teams with no GP stat should have None metrics."""
        teams = [{"team_name": "No GP Team", "rank": 1, "stats": {}}]
        today = date(2025, 12, 1)
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        assert rows[0]["gp"] is None
        assert rows[0]["avg_gp_per_day_so_far"] is None

    def test_multiple_teams_independent(self):
        """Each team's metrics are computed independently."""
        teams = [
            make_team("Team A", 40, rank=1),
            make_team("Team B", 20, rank=2),
        ]
        today = date(2025, 12, 1)
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        assert rows[0]["gp"] == 40
        assert rows[1]["gp"] == 20
        assert rows[0]["avg_gp_per_day_so_far"] != rows[1]["avg_gp_per_day_so_far"]

    def test_elapsed_and_remaining_same_for_all_teams(self):
        """elapsed_days and remaining_days must be the same across all teams."""
        teams = [make_team(f"Team {i}", i * 5, rank=i) for i in range(1, 6)]
        today = date(2025, 12, 1)
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        elapsed_values = {r["elapsed_days"] for r in rows}
        remaining_values = {r["remaining_days"] for r in rows}
        assert len(elapsed_values) == 1
        assert len(remaining_values) == 1

    def test_empty_teams_list(self):
        today = date(2025, 12, 1)
        rows, valid = compute_games_played_metrics([], SEASON_START, SEASON_END, today)
        assert valid is True
        assert rows == []

    def test_returns_correct_team_name_and_rank(self):
        teams = [make_team("Alpha", 55, rank=3)]
        today = date(2025, 12, 1)
        rows, _ = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert rows[0]["team_name"] == "Alpha"
        assert rows[0]["rank"] == 3


# ---------------------------------------------------------------------------
# Helpers for projection tests
# ---------------------------------------------------------------------------

def make_full_team(name: str, gp: int, stats: dict, rank: int = 1, roto_points=None) -> dict:
    """Create a team dict with full stats and optional roto_points."""
    base_stats = {"GP": gp}
    base_stats.update(stats)
    team = {"team_name": name, "rank": rank, "stats": base_stats}
    if roto_points is not None:
        team["roto_points"] = roto_points
    return team


# ---------------------------------------------------------------------------
# Projected totals
# ---------------------------------------------------------------------------

class TestProjectedTotals:
    def test_basic_projection(self):
        """Projected totals = (stat/gp) * projected_gp."""
        teams = [make_full_team("Team A", 100, {"PTS": 2000, "REB": 500, "AST": 300, "ST": 80, "BLK": 50, "3PTM": 150})]
        # 42 elapsed days (Oct 21 - Dec 1 inclusive), 153 total season days
        today = date(2025, 12, 1)
        rows = compute_projected_totals(teams, SEASON_START, SEASON_END, today)
        assert len(rows) == 1
        r = rows[0]
        assert r["team_name"] == "Team A"
        assert r["projected_gp"] is not None
        assert r["projected_PTS"] is not None
        # gp_per_day = 100/42, projected_gp = min(100/42 * 153, 816)
        elapsed = (today - SEASON_START).days + 1
        total_days = (SEASON_END - SEASON_START).days + 1
        expected_gp = min(100 / elapsed * total_days, 816)
        assert r["projected_gp"] == round(expected_gp)
        # PTS: (2000/100) * projected_gp
        expected_pts = (2000 / 100) * expected_gp
        assert r["projected_PTS"] == round(expected_pts)

    def test_cap_at_total_games(self):
        """If pace exceeds total_games, projected_gp should be capped."""
        # Team with very high GP early in season
        teams = [make_full_team("Fast Team", 500, {"PTS": 10000})]
        today = date(2025, 10, 27)  # 7 elapsed days
        rows = compute_projected_totals(teams, SEASON_START, SEASON_END, today, total_games=816)
        r = rows[0]
        # gp_per_day = 500/7 ≈ 71.4, projected = 71.4 * 153 ≈ 10928 > 816
        assert r["projected_gp"] == 816

    def test_zero_gp_produces_none(self):
        """Teams with 0 GP should have None projections."""
        teams = [make_full_team("No Games", 0, {"PTS": 0})]
        today = date(2025, 12, 1)
        rows = compute_projected_totals(teams, SEASON_START, SEASON_END, today)
        r = rows[0]
        assert r["projected_gp"] is None
        assert r["projected_PTS"] is None

    def test_missing_stat_produces_none_for_that_stat(self):
        """If a counting stat is missing, its projection is None but others work."""
        teams = [make_full_team("Partial", 50, {"PTS": 1000})]  # no REB, AST etc
        today = date(2025, 12, 1)
        rows = compute_projected_totals(teams, SEASON_START, SEASON_END, today)
        r = rows[0]
        assert r["projected_PTS"] is not None
        assert r["projected_REB"] is None
        assert r["projected_AST"] is None

    def test_invalid_date_returns_empty(self):
        """Before season start should return empty list."""
        teams = [make_full_team("Team A", 50, {"PTS": 1000})]
        today = date(2025, 10, 13)  # before season
        rows = compute_projected_totals(teams, SEASON_START, SEASON_END, today)
        assert rows == []

    def test_empty_teams(self):
        today = date(2025, 12, 1)
        rows = compute_projected_totals([], SEASON_START, SEASON_END, today)
        assert rows == []

    def test_custom_total_games(self):
        """Custom total_games cap is respected."""
        teams = [make_full_team("Team A", 100, {"PTS": 2000})]
        today = date(2025, 12, 1)
        rows_default = compute_projected_totals(teams, SEASON_START, SEASON_END, today, total_games=816)
        rows_low = compute_projected_totals(teams, SEASON_START, SEASON_END, today, total_games=200)
        # With low cap, projected_gp should be capped at 200
        assert rows_low[0]["projected_gp"] == 200
        # PTS should differ because of different projected_gp
        assert rows_low[0]["projected_PTS"] != rows_default[0]["projected_PTS"]


# ---------------------------------------------------------------------------
# Projected roto ranks
# ---------------------------------------------------------------------------

class TestProjectedRotoRanks:
    def _make_teams_and_projections(self):
        """Create 3 teams with known projected totals for predictable ranking."""
        teams = [
            make_full_team("High", 100, {"PTS": 3000, "REB": 600, "AST": 400, "ST": 100, "BLK": 80, "3PTM": 200},
                           rank=1, roto_points={"FG%": 3, "FT%": 2, "3PTM": 3, "PTS": 3, "REB": 3, "AST": 3, "ST": 3, "BLK": 3}),
            make_full_team("Mid", 100, {"PTS": 2000, "REB": 400, "AST": 300, "ST": 70, "BLK": 50, "3PTM": 150},
                           rank=2, roto_points={"FG%": 2, "FT%": 3, "3PTM": 2, "PTS": 2, "REB": 2, "AST": 2, "ST": 2, "BLK": 2}),
            make_full_team("Low", 100, {"PTS": 1000, "REB": 200, "AST": 100, "ST": 30, "BLK": 20, "3PTM": 80},
                           rank=3, roto_points={"FG%": 1, "FT%": 1, "3PTM": 1, "PTS": 1, "REB": 1, "AST": 1, "ST": 1, "BLK": 1}),
        ]
        today = date(2025, 12, 1)
        projected = compute_projected_totals(teams, SEASON_START, SEASON_END, today)
        return teams, projected

    def test_highest_values_get_best_rank(self):
        teams, projected = self._make_teams_and_projections()
        ranks = compute_projected_roto_ranks(projected, teams)
        by_name = {r["team_name"]: r for r in ranks}
        # "High" team should rank 3 (best of 3) in all counting categories
        assert by_name["High"]["PTS_Rank"] == 3
        assert by_name["High"]["REB_Rank"] == 3
        assert by_name["Low"]["PTS_Rank"] == 1
        assert by_name["Low"]["REB_Rank"] == 1

    def test_fg_ft_from_yahoo(self):
        """FG% and FT% ranks should come from Yahoo roto_points, not projection."""
        teams, projected = self._make_teams_and_projections()
        ranks = compute_projected_roto_ranks(projected, teams)
        by_name = {r["team_name"]: r for r in ranks}
        assert by_name["High"]["FG%_Rank"] == 3
        assert by_name["High"]["FT%_Rank"] == 2
        assert by_name["Mid"]["FT%_Rank"] == 3

    def test_projected_total_is_sum(self):
        """projected_total should be sum of all 8 category ranks."""
        teams, projected = self._make_teams_and_projections()
        ranks = compute_projected_roto_ranks(projected, teams)
        by_name = {r["team_name"]: r for r in ranks}
        for name, row in by_name.items():
            expected = sum([
                row["3PTM_Rank"], row["PTS_Rank"], row["REB_Rank"],
                row["AST_Rank"], row["ST_Rank"], row["BLK_Rank"],
                row["FG%_Rank"], row["FT%_Rank"],
            ])
            assert row["projected_total"] == expected

    def test_empty_projections(self):
        ranks = compute_projected_roto_ranks([], [])
        assert ranks == []

    def test_missing_roto_points(self):
        """Teams without roto_points should still get None for FG%/FT% ranks."""
        teams = [make_full_team("Solo", 100, {"PTS": 2000}, rank=1)]
        today = date(2025, 12, 1)
        projected = compute_projected_totals(teams, SEASON_START, SEASON_END, today)
        ranks = compute_projected_roto_ranks(projected, teams)
        assert ranks[0]["FG%_Rank"] is None
        assert ranks[0]["FT%_Rank"] is None
        # projected_total should still work with available ranks
        assert ranks[0]["projected_total"] is not None
