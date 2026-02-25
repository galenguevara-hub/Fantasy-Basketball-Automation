"""
Tests for src/fba/analysis/games_played.py
"""

from datetime import date

import pytest

from fba.analysis.games_played import compute_games_played_metrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_team(name: str, gp: int, rank: int = 1) -> dict:
    return {
        "team_name": name,
        "rank": rank,
        "stats": {"GP": gp},
    }


SEASON_START = date(2025, 10, 14)
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
        today = date(2025, 10, 14) + __import__("datetime").timedelta(days=29)
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        assert rows[0]["elapsed_days"] == 30
        assert abs(rows[0]["avg_gp_per_day_so_far"] - 30 / 30) < 1e-9

    def test_avg_needed(self):
        """avg_gp_per_day_needed = (total_games - gp) / remaining_days."""
        teams = [make_team("Team A", 30)]
        today = date(2025, 10, 14) + __import__("datetime").timedelta(days=29)
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
        today = date(2025, 10, 20)  # only 7 days elapsed
        rows, valid = compute_games_played_metrics(teams, SEASON_START, SEASON_END, today)
        assert valid is True
        # avg_so_far = 700/7 = 100, avg_needed = (816-700)/154 ≈ 0.75 → delta < 0
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
