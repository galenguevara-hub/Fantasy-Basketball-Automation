#!/usr/bin/env python3
"""
Unit tests for analysis/category_targets.py.

Uses a 4-team fixture with simple, predictable numbers to verify:
- Correct population std dev (sigma)
- Correct nearest-above / nearest-below selection
- Correct z-gap computations
- Correct target score ordering
- Tie handling
- Edge cases
"""

import math

import pytest

from fba.analysis.category_targets import (
    CATEGORIES,
    RISK_WEIGHT,
    TIE_SCORE_CAP,
    compute_category_sigma,
    compute_gaps_and_scores,
)


def _make_row(
    name: str,
    fg=None, ft=None, threes=None, pts=None,
    reb=None, ast=None, stl=None, blk=None,
    rank=None,
):
    """Helper to build a per-game row dict."""
    return {
        "team_name": name,
        "rank": rank,
        "GP": 100,
        "total_points": None,
        "FG%": fg,
        "FT%": ft,
        "3PM_pg": threes,
        "PTS_pg": pts,
        "REB_pg": reb,
        "AST_pg": ast,
        "ST_pg": stl,
        "BLK_pg": blk,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Fixture: 4 teams with known values for PTS/G.
#
#   Team A: PTS/G = 20
#   Team B: PTS/G = 18
#   Team C: PTS/G = 16
#   Team D: PTS/G = 14
#
# Population mean = 17, population variance = 5, sigma = sqrt(5) ≈ 2.2361
# ──────────────────────────────────────────────────────────────────────────────

FOUR_TEAMS = [
    _make_row("Team A", pts=20.0, fg=0.500, ft=0.800, threes=3.0, reb=10.0, ast=8.0, stl=2.0, blk=2.0),
    _make_row("Team B", pts=18.0, fg=0.480, ft=0.780, threes=2.5, reb=9.0, ast=7.0, stl=1.5, blk=1.5),
    _make_row("Team C", pts=16.0, fg=0.460, ft=0.760, threes=2.0, reb=8.0, ast=6.0, stl=1.0, blk=1.0),
    _make_row("Team D", pts=14.0, fg=0.440, ft=0.740, threes=1.5, reb=7.0, ast=5.0, stl=0.5, blk=0.5),
]


class TestComputeCategorySigma:
    """Tests for compute_category_sigma."""

    def test_sigma_pts(self):
        """Sigma for PTS/G with 4 evenly spaced teams."""
        sigmas = compute_category_sigma(FOUR_TEAMS)
        # Values: 20, 18, 16, 14 → mean=17, var=5, sigma=sqrt(5)
        expected = math.sqrt(5)
        assert sigmas["PTS_pg"] == pytest.approx(expected, abs=1e-6)

    def test_sigma_fg_pct(self):
        """Sigma for FG% with 4 teams."""
        sigmas = compute_category_sigma(FOUR_TEAMS)
        # Values: 0.500, 0.480, 0.460, 0.440 → mean=0.470
        # var = ((0.03^2 + 0.01^2 + 0.01^2 + 0.03^2) / 4) = 0.0005
        expected = math.sqrt(0.0005)
        assert sigmas["FG%"] == pytest.approx(expected, abs=1e-8)

    def test_sigma_all_same(self):
        """Sigma is None when all teams have the same value."""
        rows = [
            _make_row("A", pts=10.0),
            _make_row("B", pts=10.0),
            _make_row("C", pts=10.0),
        ]
        sigmas = compute_category_sigma(rows)
        assert sigmas["PTS_pg"] is None

    def test_sigma_single_team(self):
        """Sigma is None with only 1 team (need at least 2)."""
        rows = [_make_row("A", pts=10.0)]
        sigmas = compute_category_sigma(rows)
        assert sigmas["PTS_pg"] is None

    def test_sigma_with_none_values(self):
        """None values are excluded from sigma calculation."""
        rows = [
            _make_row("A", pts=20.0),
            _make_row("B", pts=10.0),
            _make_row("C", pts=None),  # excluded
        ]
        sigmas = compute_category_sigma(rows)
        # Values: 20, 10 → mean=15, var=25, sigma=5
        assert sigmas["PTS_pg"] == pytest.approx(5.0, abs=1e-6)


class TestGapComputations:
    """Tests for correct gap-to-gain and gap-to-lose."""

    def test_gap_up_for_middle_team(self):
        """Team C (16 PTS/G) should gap up to Team B (18 PTS/G)."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_c = result["Team C"]
        pts_entry = _find_cat(team_c, "PTS/G")

        assert pts_entry["next_better_team"] == "Team B"
        assert pts_entry["next_better_value"] == 18.0
        assert pts_entry["gap_up"] == pytest.approx(2.0)

    def test_gap_down_for_middle_team(self):
        """Team C (16 PTS/G) should gap down to Team D (14 PTS/G)."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_c = result["Team C"]
        pts_entry = _find_cat(team_c, "PTS/G")

        assert pts_entry["next_worse_team"] == "Team D"
        assert pts_entry["next_worse_value"] == 14.0
        assert pts_entry["gap_down"] == pytest.approx(2.0)

    def test_best_team_has_no_gap_up(self):
        """Team A (best in PTS/G) should have z_gap_up = None."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_a = result["Team A"]
        pts_entry = _find_cat(team_a, "PTS/G")

        assert pts_entry["z_gap_up"] is None
        assert pts_entry["next_better_team"] is None
        # 1st place with a valid z_gap_down gets a defensive score
        assert pts_entry["target_score"] is not None
        assert pts_entry["target_score"] > 0

    def test_worst_team_has_no_gap_down(self):
        """Team D (worst in PTS/G) should have z_gap_down = None."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_d = result["Team D"]
        pts_entry = _find_cat(team_d, "PTS/G")

        assert pts_entry["z_gap_down"] is None
        assert pts_entry["next_worse_team"] is None

    def test_z_gap_up_computation(self):
        """Verify z_gap_up = gap_up / sigma for Team C PTS/G."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_c = result["Team C"]
        pts_entry = _find_cat(team_c, "PTS/G")

        sigma = math.sqrt(5)
        expected_z = 2.0 / sigma
        assert pts_entry["z_gap_up"] == pytest.approx(expected_z, abs=1e-6)

    def test_z_gap_down_computation(self):
        """Verify z_gap_down = gap_down / sigma for Team C PTS/G."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_c = result["Team C"]
        pts_entry = _find_cat(team_c, "PTS/G")

        sigma = math.sqrt(5)
        expected_z = 2.0 / sigma
        assert pts_entry["z_gap_down"] == pytest.approx(expected_z, abs=1e-6)


class TestRankAssignment:
    """Tests for rank assignment within analysis."""

    def test_ranks_assigned_correctly(self):
        """Best team gets rank N, worst gets rank 1."""
        result = compute_gaps_and_scores(FOUR_TEAMS)

        # Team A is best in PTS/G (20) → rank 4
        assert _find_cat(result["Team A"], "PTS/G")["rank"] == 4
        # Team D is worst (14) → rank 1
        assert _find_cat(result["Team D"], "PTS/G")["rank"] == 1


class TestTieHandling:
    """Tests for tie scenarios."""

    def test_tie_skips_equal_values(self):
        """When two teams tie, next_better should skip the tied value."""
        rows = [
            _make_row("Alpha", pts=20.0, fg=0.500, ft=0.800, threes=3.0, reb=10.0, ast=8.0, stl=2.0, blk=2.0),
            _make_row("Bravo", pts=18.0, fg=0.480, ft=0.780, threes=2.5, reb=9.0, ast=7.0, stl=1.5, blk=1.5),
            _make_row("Charlie", pts=18.0, fg=0.460, ft=0.760, threes=2.0, reb=8.0, ast=6.0, stl=1.0, blk=1.0),  # tied with Bravo
            _make_row("Delta", pts=14.0, fg=0.440, ft=0.740, threes=1.5, reb=7.0, ast=5.0, stl=0.5, blk=0.5),
        ]
        result = compute_gaps_and_scores(rows)

        # Bravo (18) tied with Charlie (18).
        # Bravo's next_better should be Alpha (20), not Charlie.
        bravo_pts = _find_cat(result["Bravo"], "PTS/G")
        assert bravo_pts["next_better_team"] == "Alpha"
        assert bravo_pts["gap_up"] == pytest.approx(2.0)

        # Charlie (18) tied with Bravo (18).
        # Charlie's next_better should also be Alpha (20), skipping Bravo.
        charlie_pts = _find_cat(result["Charlie"], "PTS/G")
        assert charlie_pts["next_better_team"] == "Alpha"
        assert charlie_pts["gap_up"] == pytest.approx(2.0)

    def test_tie_best_in_category(self):
        """If a team is tied for best, z_gap_up should be None (no strictly better)."""
        rows = [
            _make_row("Alpha", pts=20.0, fg=0.500, ft=0.800, threes=3.0, reb=10.0, ast=8.0, stl=2.0, blk=2.0),
            _make_row("Bravo", pts=20.0, fg=0.480, ft=0.780, threes=2.5, reb=9.0, ast=7.0, stl=1.5, blk=1.5),  # tied for best
        ]
        result = compute_gaps_and_scores(rows)

        alpha_pts = _find_cat(result["Alpha"], "PTS/G")
        assert alpha_pts["z_gap_up"] is None
        # Both tied for best with no one below in PTS → z_gap_down is None → score is None
        assert alpha_pts["target_score"] is None

        bravo_pts = _find_cat(result["Bravo"], "PTS/G")
        assert bravo_pts["z_gap_up"] is None
        assert bravo_pts["target_score"] is None


class TestTargetScore:
    """Tests for target score computation and ordering."""

    def test_score_formula(self):
        """Verify score = 1/z_gap_up + 0.25 * z_gap_down."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_b = result["Team B"]
        pts_entry = _find_cat(team_b, "PTS/G")

        sigma = math.sqrt(5)
        z_up = 2.0 / sigma   # gap to Team A
        z_down = 2.0 / sigma  # gap from Team C

        expected_score = (1.0 / z_up) + RISK_WEIGHT * z_down
        assert pts_entry["target_score"] == pytest.approx(expected_score, abs=1e-6)

    def test_best_team_gets_defensive_score(self):
        """Team that is best in category gets a defensive score based on z_gap_down."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_a = result["Team A"]
        pts_entry = _find_cat(team_a, "PTS/G")
        # 1st place with a valid z_gap_down: score = DEFEND_WEIGHT / max(z_gap_down, EPS)
        assert pts_entry["target_score"] is not None
        assert pts_entry["target_score"] > 0

    def test_score_ordering_favors_smaller_gap(self):
        """A team closer to the next rank should have a higher score."""
        rows = [
            _make_row("Alpha", pts=20.0, fg=0.500, ft=0.800, threes=3.0, reb=10.0, ast=8.0, stl=2.0, blk=2.0),
            _make_row("Bravo", pts=19.5, fg=0.480, ft=0.780, threes=2.5, reb=9.0, ast=7.0, stl=1.5, blk=1.5),  # close to Alpha in PTS
            _make_row("Charlie", pts=10.0, fg=0.460, ft=0.760, threes=2.0, reb=8.0, ast=6.0, stl=1.0, blk=1.0),  # far from Bravo in PTS
        ]
        result = compute_gaps_and_scores(rows)

        bravo_pts = _find_cat(result["Bravo"], "PTS/G")
        charlie_pts = _find_cat(result["Charlie"], "PTS/G")

        # Bravo has small gap to Alpha → higher score
        # Charlie has large gap to Bravo → lower score
        assert bravo_pts["target_score"] > charlie_pts["target_score"]


class TestRecommendationTags:
    """Tests for TARGET / DEFEND tag assignment."""

    def test_tags_assigned(self):
        """Each team should have TARGET and DEFEND tags."""
        result = compute_gaps_and_scores(FOUR_TEAMS)

        # Team B (middle team with scores for most categories)
        team_b = result["Team B"]

        target_count = sum(1 for c in team_b if c["is_target"])
        defend_count = sum(1 for c in team_b if c["is_defend"])

        assert target_count <= 3
        assert defend_count <= 3
        assert target_count > 0  # should have at least 1 target

    def test_target_has_highest_scores(self):
        """TARGET tags should be on the categories with highest target_score."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_c = result["Team C"]

        scored = [c for c in team_c if c["target_score"] is not None and c["z_gap_up"] is not None]
        scored.sort(key=lambda c: (-c["target_score"], c["category"]))

        target_cats = {c["category"] for c in team_c if c["is_target"]}
        top_3_cats = {c["category"] for c in scored[:3]}

        assert target_cats == top_3_cats

    def test_defend_has_smallest_buffer(self):
        """DEFEND tags should be on categories with smallest z_gap_down (independent of TARGET)."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        team_b = result["Team B"]

        defend_cats = [c for c in team_b if c["is_defend"]]

        # Verify they have the smallest z_gap_down among all categories
        with_gap = [
            c for c in team_b
            if c["z_gap_down"] is not None
        ]
        with_gap.sort(key=lambda c: (c["z_gap_down"], c["category"]))

        defend_cat_names = {c["category"] for c in defend_cats}
        expected = {c["category"] for c in with_gap[:3]}
        assert defend_cat_names == expected

    def test_category_can_be_both_target_and_defend(self):
        """A category can be both TARGET and DEFEND simultaneously."""
        result = compute_gaps_and_scores(FOUR_TEAMS)
        # Check across all teams if any category has both flags
        for team_name, cats in result.items():
            for c in cats:
                if c["is_target"] and c["is_defend"]:
                    # Found one — both flags are set, test passes
                    return
        # If no overlap found in this dataset, just verify the flags are independent
        # by checking that defend doesn't exclude targets
        for team_name, cats in result.items():
            target_cats = {c["category"] for c in cats if c["is_target"]}
            defend_cats = {c["category"] for c in cats if c["is_defend"]}
            # Defend should be based on z_gap_down, not filtered by target status
            with_gap = [c for c in cats if c["z_gap_down"] is not None]
            with_gap.sort(key=lambda c: (c["z_gap_down"], c["category"]))
            expected_defend = {c["category"] for c in with_gap[:3]}
            assert defend_cats == expected_defend


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_rows(self):
        """Empty input returns empty result."""
        assert compute_gaps_and_scores([]) == {}
        # sigma still iterates all categories, returning None for each.
        sigmas = compute_category_sigma([])
        for cat in CATEGORIES:
            assert sigmas[cat["key"]] is None

    def test_single_team(self):
        """Single team: all gaps are None, all scores are None."""
        rows = [
            _make_row("Solo", pts=20.0, fg=0.500, ft=0.800, threes=3.0, reb=10.0, ast=8.0, stl=2.0, blk=2.0),
        ]
        result = compute_gaps_and_scores(rows)
        solo = result["Solo"]

        for entry in solo:
            assert entry["z_gap_up"] is None
            assert entry["z_gap_down"] is None
            assert entry["target_score"] is None

    def test_missing_category_value(self):
        """Team with None for a category gets None for all fields of that category."""
        rows = [
            _make_row("A", pts=20.0, fg=0.500, ft=0.800, threes=3.0, reb=10.0, ast=8.0, stl=2.0, blk=2.0),
            _make_row("B", pts=None, fg=0.480, ft=0.780, threes=2.5, reb=9.0, ast=7.0, stl=1.5, blk=1.5),  # PTS is None
        ]
        result = compute_gaps_and_scores(rows)
        b_pts = _find_cat(result["B"], "PTS/G")
        assert b_pts["value"] is None
        assert b_pts["gap_up"] is None
        assert b_pts["z_gap_up"] is None

    def test_all_teams_tied(self):
        """All teams have the same value: sigma=None, all gaps None."""
        rows = [
            _make_row("A", pts=15.0),
            _make_row("B", pts=15.0),
            _make_row("C", pts=15.0),
        ]
        sigmas = compute_category_sigma(rows)
        assert sigmas["PTS_pg"] is None

        result = compute_gaps_and_scores(rows)
        for team_name in ["A", "B", "C"]:
            pts_entry = _find_cat(result[team_name], "PTS/G")
            assert pts_entry["z_gap_up"] is None
            assert pts_entry["z_gap_down"] is None
            assert pts_entry["target_score"] is None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _find_cat(entries: list, category_name: str) -> dict:
    """Find a category entry by name."""
    for e in entries:
        if e["category"] == category_name:
            return e
    raise ValueError(f"Category {category_name!r} not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
