#!/usr/bin/env python3
"""
Unit tests for normalization and ranking logic.

Tests cover:
- Parsing stat values (strings, numbers, None)
- Per-game calculations
- Ranking with tie-breaking
- Edge cases (missing GP, missing stats)
"""

import pytest

from fba.normalize import (
    build_per_game_rows,
    calculate_per_game_stats,
    parse_stat_value,
    rank_teams_by_category,
    normalize_standings,
)


class TestParseStatValue:
    """Test stat value parsing."""

    def test_parse_integer(self):
        """Parse integer stat values."""
        assert parse_stat_value(664) == 664.0
        assert parse_stat_value(673) == 673.0

    def test_parse_float(self):
        """Parse float stat values."""
        assert parse_stat_value(0.476) == 0.476
        assert parse_stat_value(0.821) == 0.821

    def test_parse_string_with_comma(self):
        """Parse strings with comma separators."""
        assert parse_stat_value("1,256") == 1256.0
        assert parse_stat_value("12,402") == 12402.0

    def test_parse_string_number(self):
        """Parse string numbers without commas."""
        assert parse_stat_value("673") == 673.0
        assert parse_stat_value("0.5") == 0.5

    def test_parse_none(self):
        """Parse None values."""
        assert parse_stat_value(None) is None

    def test_parse_empty_string(self):
        """Parse empty strings."""
        assert parse_stat_value("") is None
        assert parse_stat_value("—") is None

    def test_parse_invalid(self):
        """Parse invalid values."""
        assert parse_stat_value("invalid") is None


class TestCalculatePerGameStats:
    """Test per-game stat calculations."""

    def test_basic_calculation(self):
        """Calculate per-game stats for a team."""
        team = {
            "team_name": "Team A",
            "stats": {
                "GP": 664,
                "PTS": "12,402",
                "REB": "4,111",
                "AST": "3,008",
                "ST": 673,
                "BLK": 460,
                "3PTM": "1,256",
            },
        }

        pg_stats = calculate_per_game_stats(team)

        # Verify calculations
        assert abs(pg_stats["PTS_pg"] - (12402 / 664)) < 0.01
        assert abs(pg_stats["REB_pg"] - (4111 / 664)) < 0.01
        assert abs(pg_stats["AST_pg"] - (3008 / 664)) < 0.01
        assert abs(pg_stats["ST_pg"] - (673 / 664)) < 0.01
        assert abs(pg_stats["BLK_pg"] - (460 / 664)) < 0.01
        assert abs(pg_stats["3PM_pg"] - (1256 / 664)) < 0.01

    def test_missing_gp(self):
        """Handle teams with missing GP."""
        team = {
            "team_name": "Team B",
            "stats": {"PTS": "12,000", "REB": "4,000"},
        }

        pg_stats = calculate_per_game_stats(team)

        # All should be None
        assert pg_stats["PTS_pg"] is None
        assert pg_stats["REB_pg"] is None

    def test_gp_zero(self):
        """Handle teams with GP=0."""
        team = {
            "team_name": "Team C",
            "stats": {
                "GP": 0,
                "PTS": "12,000",
                "REB": "4,000",
            },
        }

        pg_stats = calculate_per_game_stats(team)

        # All should be None (avoid division by zero)
        assert pg_stats["PTS_pg"] is None
        assert pg_stats["REB_pg"] is None

    def test_missing_stats(self):
        """Handle teams with missing individual stats."""
        team = {
            "team_name": "Team D",
            "stats": {
                "GP": 100,
                "PTS": "1,000",
                # REB missing
            },
        }

        pg_stats = calculate_per_game_stats(team)

        assert pg_stats["PTS_pg"] == 10.0
        assert pg_stats["REB_pg"] is None


class TestBuildPerGameRows:
    """Test building per-game row data."""

    def test_build_rows_with_percentages(self):
        """Build per-game rows including percentage stats."""
        teams = [
            {
                "team_name": "Team A",
                "rank": 1,
                "stats": {
                    "GP": 664,
                    "PTS": "12,402",
                    "REB": "4,111",
                    "AST": "3,008",
                    "ST": 673,
                    "BLK": 460,
                    "3PTM": "1,256",
                    "FG%": 0.476,
                    "FT%": 0.821,
                },
            }
        ]

        rows = build_per_game_rows(teams)

        assert len(rows) == 1
        row = rows[0]
        assert row["team_name"] == "Team A"
        assert row["rank"] == 1
        assert row["GP"] == 664
        assert row["FG%"] == 0.476
        assert row["FT%"] == 0.821
        assert abs(row["PTS_pg"] - (12402 / 664)) < 0.01

    def test_preserve_team_order(self):
        """Verify that team order is preserved."""
        teams = [
            {
                "team_name": "Team A",
                "rank": 1,
                "stats": {"GP": 100, "PTS": "1,000"},
            },
            {
                "team_name": "Team B",
                "rank": 2,
                "stats": {"GP": 100, "PTS": "1,100"},
            },
            {
                "team_name": "Team C",
                "rank": 3,
                "stats": {"GP": 100, "PTS": "1,200"},
            },
        ]

        rows = build_per_game_rows(teams)

        assert len(rows) == 3
        assert rows[0]["team_name"] == "Team A"
        assert rows[1]["team_name"] == "Team B"
        assert rows[2]["team_name"] == "Team C"


class TestRankTeamsByCategory:
    """Test ranking logic."""

    def test_basic_ranking(self):
        """Rank teams by category correctly."""
        per_game_rows = [
            {
                "team_name": "Team A",
                "rank": 1,
                "PTS_pg": 15.0,
                "REB_pg": 10.0,
                "AST_pg": 5.0,
                "ST_pg": 1.5,
                "BLK_pg": 1.0,
                "3PM_pg": 2.0,
                "FG%": 0.480,
                "FT%": 0.820,
            },
            {
                "team_name": "Team B",
                "rank": 2,
                "PTS_pg": 16.0,
                "REB_pg": 9.0,
                "AST_pg": 6.0,
                "ST_pg": 1.4,
                "BLK_pg": 1.1,
                "3PM_pg": 1.8,
                "FG%": 0.475,
                "FT%": 0.825,
            },
        ]

        ranking_rows = rank_teams_by_category(per_game_rows)

        assert len(ranking_rows) == 2

        # Team B should rank best in PTS (16.0 > 15.0) with N=best.
        team_b = [r for r in ranking_rows if r["team_name"] == "Team B"][0]
        assert team_b["PTS_Rank"] == 2

        # Team A should rank worst in PTS with 2 teams.
        team_a = [r for r in ranking_rows if r["team_name"] == "Team A"][0]
        assert team_a["PTS_Rank"] == 1

    def test_tie_breaking_by_team_name(self):
        """Tie-break by team name (alphabetical)."""
        per_game_rows = [
            {
                "team_name": "Zebras",
                "rank": 1,
                "PTS_pg": 15.0,
                "REB_pg": 10.0,
                "AST_pg": 5.0,
                "ST_pg": 1.5,
                "BLK_pg": 1.0,
                "3PM_pg": 2.0,
                "FG%": 0.480,
                "FT%": 0.820,
            },
            {
                "team_name": "Alpacas",
                "rank": 2,
                "PTS_pg": 15.0,  # Same as Zebras
                "REB_pg": 10.0,
                "AST_pg": 5.0,
                "ST_pg": 1.5,
                "BLK_pg": 1.0,
                "3PM_pg": 2.0,
                "FG%": 0.480,
                "FT%": 0.820,
            },
        ]

        ranking_rows = rank_teams_by_category(per_game_rows)

        # Both have same PTS_pg, so Alpacas (alphabetically first) should rank best (=2).
        alpacas = [r for r in ranking_rows if r["team_name"] == "Alpacas"][0]
        zebras = [r for r in ranking_rows if r["team_name"] == "Zebras"][0]

        assert alpacas["PTS_Rank"] == 2
        assert zebras["PTS_Rank"] == 1

    def test_none_values_rank_last(self):
        """None values rank last."""
        per_game_rows = [
            {
                "team_name": "Team A",
                "rank": 1,
                "PTS_pg": 15.0,
                "REB_pg": 10.0,
                "AST_pg": 5.0,
                "ST_pg": 1.5,
                "BLK_pg": 1.0,
                "3PM_pg": 2.0,
                "FG%": 0.480,
                "FT%": 0.820,
            },
            {
                "team_name": "Team B",
                "rank": 2,
                "PTS_pg": None,  # Missing
                "REB_pg": 10.0,
                "AST_pg": 5.0,
                "ST_pg": 1.5,
                "BLK_pg": 1.0,
                "3PM_pg": 2.0,
                "FG%": 0.480,
                "FT%": 0.820,
            },
        ]

        ranking_rows = rank_teams_by_category(per_game_rows)

        team_a = [r for r in ranking_rows if r["team_name"] == "Team A"][0]
        team_b = [r for r in ranking_rows if r["team_name"] == "Team B"][0]

        # Team A should rank best (has value) with N=best.
        assert team_a["PTS_Rank"] == 2
        # Team B should rank worst (None).
        assert team_b["PTS_Rank"] == 1

    def test_all_percentages_use_same_logic(self):
        """Percentages are ranked by same logic (higher is better)."""
        per_game_rows = [
            {
                "team_name": "Team A",
                "rank": 1,
                "PTS_pg": 10.0,
                "REB_pg": 10.0,
                "AST_pg": 10.0,
                "ST_pg": 1.0,
                "BLK_pg": 1.0,
                "3PM_pg": 1.0,
                "FG%": 0.450,
                "FT%": 0.800,
            },
            {
                "team_name": "Team B",
                "rank": 2,
                "PTS_pg": 10.0,
                "REB_pg": 10.0,
                "AST_pg": 10.0,
                "ST_pg": 1.0,
                "BLK_pg": 1.0,
                "3PM_pg": 1.0,
                "FG%": 0.480,  # Higher
                "FT%": 0.820,  # Higher
            },
        ]

        ranking_rows = rank_teams_by_category(per_game_rows)

        team_b = [r for r in ranking_rows if r["team_name"] == "Team B"][0]
        assert team_b["FG%_Rank"] == 2
        assert team_b["FT%_Rank"] == 2


class TestIntegration:
    """Integration tests for the full normalization pipeline."""

    def test_normalize_standings_complete_flow(self):
        """Test full normalization from raw teams to per-game and rankings."""
        teams = [
            {
                "team_name": "Team Alpha",
                "rank": 1,
                "total_points": 62,
                "pts_change": 0,
                "roto_points": {"PTS": 9},
                "stats": {
                    "GP": 664,
                    "FG%": 0.476,
                    "FT%": 0.821,
                    "3PTM": "1,256",
                    "PTS": "12,402",
                    "REB": "4,111",
                    "AST": "3,008",
                    "ST": 673,
                    "BLK": 460,
                },
            },
            {
                "team_name": "Team Beta",
                "rank": 2,
                "total_points": 59,
                "pts_change": 0,
                "roto_points": {"PTS": 8},
                "stats": {
                    "GP": 680,
                    "FG%": 0.478,
                    "FT%": 0.789,
                    "3PTM": "1,275",
                    "PTS": "12,224",
                    "REB": "4,478",
                    "AST": "2,690",
                    "ST": 683,
                    "BLK": 477,
                },
            },
        ]

        result = normalize_standings(teams)

        assert "per_game_rows" in result
        assert "ranking_rows" in result

        per_game_rows = result["per_game_rows"]
        ranking_rows = result["ranking_rows"]

        assert len(per_game_rows) == 2
        assert len(ranking_rows) == 2

        # Verify per-game data
        alpha_pg = per_game_rows[0]
        assert alpha_pg["team_name"] == "Team Alpha"
        assert alpha_pg["GP"] == 664
        assert alpha_pg["FG%"] == 0.476

        # Verify rankings are present
        alpha_rank = ranking_rows[0]
        assert alpha_rank["team_name"] == "Team Alpha"
        assert "PTS_Rank" in alpha_rank
        assert "FG%_Rank" in alpha_rank


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_teams_list(self):
        """Handle empty teams list."""
        result = normalize_standings([])

        assert result["per_game_rows"] == []
        assert result["ranking_rows"] == []

    def test_single_team(self):
        """Handle single team (should rank 1)."""
        teams = [
            {
                "team_name": "Only Team",
                "rank": 1,
                "stats": {
                    "GP": 100,
                    "PTS": "1,000",
                    "REB": "500",
                    "AST": "300",
                    "ST": 100,
                    "BLK": 50,
                    "3PTM": "200",
                    "FG%": 0.450,
                    "FT%": 0.800,
                },
            }
        ]

        result = normalize_standings(teams)

        ranking_row = result["ranking_rows"][0]
        assert ranking_row["PTS_Rank"] == 1
        assert ranking_row["FG%_Rank"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
