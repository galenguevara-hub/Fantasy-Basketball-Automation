#!/usr/bin/env python3
"""
Manual test runner for normalization logic (no pytest required).
Verifies all core functionality works correctly.
"""

from fba.normalize import (
    parse_stat_value,
    calculate_per_game_stats,
    build_per_game_rows,
    rank_teams_by_category,
    normalize_standings,
)


def test_parse_stat_value():
    """Test stat value parsing."""
    print("Testing parse_stat_value...")
    assert parse_stat_value(664) == 664.0
    assert parse_stat_value(0.476) == 0.476
    assert parse_stat_value("1,256") == 1256.0
    assert parse_stat_value("673") == 673.0
    assert parse_stat_value(None) is None
    assert parse_stat_value("") is None
    assert parse_stat_value("—") is None
    print("  ✓ parse_stat_value tests passed")


def test_calculate_per_game_stats():
    """Test per-game stat calculations."""
    print("Testing calculate_per_game_stats...")

    # Test basic calculation
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
    assert abs(pg_stats["PTS_pg"] - (12402 / 664)) < 0.01
    assert abs(pg_stats["REB_pg"] - (4111 / 664)) < 0.01

    # Test missing GP
    team_no_gp = {"team_name": "Team B", "stats": {"PTS": "12,000"}}
    pg_stats_no_gp = calculate_per_game_stats(team_no_gp)
    assert pg_stats_no_gp["PTS_pg"] is None

    print("  ✓ calculate_per_game_stats tests passed")


def test_build_per_game_rows():
    """Test building per-game row data."""
    print("Testing build_per_game_rows...")

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

    print("  ✓ build_per_game_rows tests passed")


def test_ranking():
    """Test ranking logic."""
    print("Testing rank_teams_by_category...")

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

    # Team B should rank 1st in PTS (16.0 > 15.0)
    team_b = [r for r in ranking_rows if r["team_name"] == "Team B"][0]
    assert team_b["PTS_Rank"] == 1

    # Team A should rank 2nd in PTS
    team_a = [r for r in ranking_rows if r["team_name"] == "Team A"][0]
    assert team_a["PTS_Rank"] == 2

    print("  ✓ rank_teams_by_category tests passed")


def test_tie_breaking():
    """Test tie-breaking by team name."""
    print("Testing tie-breaking logic...")

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
            "PTS_pg": 15.0,  # Same as Zebras - tie
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

    # Alpacas (alphabetically first) should rank 1
    alpacas = [r for r in ranking_rows if r["team_name"] == "Alpacas"][0]
    zebras = [r for r in ranking_rows if r["team_name"] == "Zebras"][0]

    assert alpacas["PTS_Rank"] == 1, f"Expected Alpacas to rank 1, got {alpacas['PTS_Rank']}"
    assert zebras["PTS_Rank"] == 2, f"Expected Zebras to rank 2, got {zebras['PTS_Rank']}"

    print("  ✓ tie-breaking tests passed")


def test_none_values_rank_last():
    """Test that None values rank last."""
    print("Testing None value handling...")

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

    assert team_a["PTS_Rank"] == 1, f"Expected Team A rank 1, got {team_a['PTS_Rank']}"
    assert team_b["PTS_Rank"] == 2, f"Expected Team B rank 2, got {team_b['PTS_Rank']}"

    print("  ✓ None value handling tests passed")


def test_full_integration():
    """Test full normalization pipeline."""
    print("Testing full normalize_standings integration...")

    teams = [
        {
            "team_name": "Stealy Dan-iels",
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
            "team_name": "J-Dub 13 and The Portis",
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

    per_game_rows = result["per_game_rows"]
    ranking_rows = result["ranking_rows"]

    assert len(per_game_rows) == 2
    assert len(ranking_rows) == 2

    # Verify per-game data
    row1 = per_game_rows[0]
    assert row1["team_name"] == "Stealy Dan-iels"
    assert row1["GP"] == 664
    assert row1["FG%"] == 0.476

    # Verify rankings exist
    rank1 = ranking_rows[0]
    assert "PTS_Rank" in rank1
    assert "FG%_Rank" in rank1

    print("  ✓ full integration tests passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("NORMALIZATION TEST SUITE")
    print("=" * 60 + "\n")

    try:
        test_parse_stat_value()
        test_calculate_per_game_stats()
        test_build_per_game_rows()
        test_ranking()
        test_tie_breaking()
        test_none_values_rank_last()
        test_full_integration()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60 + "\n")
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
