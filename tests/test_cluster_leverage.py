#!/usr/bin/env python3
"""
Unit tests for analysis/cluster_leverage.py.

Fixtures:
- CLUSTERED_ABOVE: Team D (PTS=20) has 3 tiers tightly packed above it,
  all within T=0.75 sigma.  Verifies points_up_within_T=3 and z_to_gain_2/3.
- TIES_FIXTURE: Two teams share a value; verifies tier deduplication produces
  non-zero z_to_gain_1 (no fake zero-gap gains).
"""

import math

import pytest

from fba.analysis.cluster_leverage import (
    T_DEFAULT,
    _weighted_score,
    compute_cluster_metrics,
    compute_tiers,
)


# ──────────────────────────────────────────────────────────────────────────────
# Row factory (mirrors the one in test_category_targets.py)
# ──────────────────────────────────────────────────────────────────────────────

def _make_row(
    name: str,
    fg=None, ft=None, threes=None, pts=None,
    reb=None, ast=None, stl=None, blk=None,
    rank=None,
):
    """Build a minimal per-game row dict."""
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
# CLUSTERED_ABOVE fixture
#
# PTS/G: A=21, B=20.5, C=20.3, D=20, E=15
# sigma(PTS): sqrt(4.8584) ≈ 2.2042
# T_DEFAULT = 0.75 → T*sigma ≈ 1.653
#
# For Team D (20, tier_idx=3):
#   Tier above at idx 2 (20.3): (20.3-20)/sigma ≈ 0.136 ≤ 0.75 ✓
#   Tier above at idx 1 (20.5): (20.5-20)/sigma ≈ 0.227 ≤ 0.75 ✓
#   Tier above at idx 0 (21.0): (21.0-20)/sigma ≈ 0.454 ≤ 0.75 ✓
#   → points_up_within_T = 3
#   Tier below at idx 4 (15.0): (20-15)/sigma   ≈ 2.269 > 0.75  ✗
#   → points_down_within_T = 0
# ──────────────────────────────────────────────────────────────────────────────

CLUSTERED_ABOVE = [
    _make_row("Team A", pts=21.0, fg=0.500, ft=0.800, threes=3.0, reb=10.0, ast=8.0, stl=2.0, blk=2.0),
    _make_row("Team B", pts=20.5, fg=0.480, ft=0.780, threes=2.5, reb=9.0,  ast=7.0, stl=1.5, blk=1.5),
    _make_row("Team C", pts=20.3, fg=0.460, ft=0.760, threes=2.0, reb=8.0,  ast=6.0, stl=1.0, blk=1.0),
    _make_row("Team D", pts=20.0, fg=0.440, ft=0.740, threes=1.5, reb=7.0,  ast=5.0, stl=0.5, blk=0.5),
    _make_row("Team E", pts=15.0, fg=0.420, ft=0.720, threes=1.0, reb=6.0,  ast=4.0, stl=0.3, blk=0.3),
]

# PTS sigma for CLUSTERED_ABOVE (verified manually):
# values = [21, 20.5, 20.3, 20, 15]; mean = 96.8/5 = 19.36
# variance = (1.64² + 1.14² + 0.94² + 0.64² + 4.36²) / 5 = 24.292/5 = 4.8584
_CLUSTER_SIGMA = math.sqrt(4.8584)


# ──────────────────────────────────────────────────────────────────────────────
# TIES_FIXTURE
#
# PTS/G: Alpha=20, Bravo=18, Charlie=18 (tied), Delta=14
# Tiers: [20, 18, 14]  (3 distinct values)
# sigma([20, 18, 18, 14]): mean=17.5, var=(6.25+.25+.25+12.25)/4=19/4=4.75
#   sigma = sqrt(4.75) ≈ 2.179
#
# For Bravo (18, tier_idx=1):
#   z_to_gain_1 = (20 - 18) / sigma = 2/2.179 ≈ 0.918  (non-zero ✓)
# For Charlie (18, tier_idx=1): same as Bravo
# ──────────────────────────────────────────────────────────────────────────────

TIES_FIXTURE = [
    _make_row("Alpha",   pts=20.0, fg=0.500, ft=0.800, threes=3.0, reb=10.0, ast=8.0, stl=2.0, blk=2.0),
    _make_row("Bravo",   pts=18.0, fg=0.480, ft=0.780, threes=2.5, reb=9.0,  ast=7.0, stl=1.5, blk=1.5),
    _make_row("Charlie", pts=18.0, fg=0.460, ft=0.760, threes=2.0, reb=8.0,  ast=6.0, stl=1.0, blk=1.0),
    _make_row("Delta",   pts=14.0, fg=0.440, ft=0.740, threes=1.5, reb=7.0,  ast=5.0, stl=0.5, blk=0.5),
]

_TIES_SIGMA = math.sqrt(4.75)  # sigma for TIES_FIXTURE PTS/G


# ══════════════════════════════════════════════════════════════════════════════
# TestComputeTiers
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeTiers:
    """Tests for compute_tiers()."""

    def test_basic_descending_order(self):
        tiers = compute_tiers({"A": 20.0, "B": 18.0, "C": 16.0})
        assert tiers == [20.0, 18.0, 16.0]

    def test_tie_deduplication(self):
        """Equal values produce a single tier entry."""
        tiers = compute_tiers({"A": 20.0, "B": 18.0, "C": 18.0, "D": 14.0})
        assert tiers == [20.0, 18.0, 14.0]

    def test_none_values_excluded(self):
        tiers = compute_tiers({"A": 20.0, "B": None, "C": 16.0})
        assert tiers == [20.0, 16.0]

    def test_all_same_value_is_one_tier(self):
        tiers = compute_tiers({"A": 15.0, "B": 15.0, "C": 15.0})
        assert tiers == [15.0]

    def test_empty_dict(self):
        assert compute_tiers({}) == []

    def test_all_none(self):
        assert compute_tiers({"A": None, "B": None}) == []

    def test_single_non_none(self):
        assert compute_tiers({"A": 10.0}) == [10.0]


# ══════════════════════════════════════════════════════════════════════════════
# TestClusteredAbove — primary integration fixture
# ══════════════════════════════════════════════════════════════════════════════

class TestClusteredAbove:
    """Team D with 3 tiers tightly clustered above."""

    @pytest.fixture(autouse=True)
    def _compute(self):
        self.result = compute_cluster_metrics(CLUSTERED_ABOVE)
        self.d = self.result["Team D"]["PTS/G"]
        self.sigma = self.d["sigma"]

    # ── sigma ──────────────────────────────────────────────────────────────

    def test_sigma_correct(self):
        assert self.sigma == pytest.approx(_CLUSTER_SIGMA, abs=1e-4)

    # ── z_to_gain_k ────────────────────────────────────────────────────────

    def test_z_to_gain_1(self):
        """z to +1 = (20.3 - 20) / sigma."""
        expected = (20.3 - 20.0) / self.sigma
        assert self.d["z_to_gain_1"] == pytest.approx(expected, abs=1e-6)

    def test_z_to_gain_2(self):
        """z to +2 = (20.5 - 20) / sigma."""
        expected = (20.5 - 20.0) / self.sigma
        assert self.d["z_to_gain_2"] == pytest.approx(expected, abs=1e-6)

    def test_z_to_gain_3(self):
        """z to +3 = (21.0 - 20) / sigma."""
        expected = (21.0 - 20.0) / self.sigma
        assert self.d["z_to_gain_3"] == pytest.approx(expected, abs=1e-6)

    def test_z_to_gain_3_lte_threshold(self):
        """All 3 tiers above must be within T_DEFAULT to trigger count=3."""
        assert self.d["z_to_gain_3"] < T_DEFAULT

    # ── points up ─────────────────────────────────────────────────────────

    def test_points_up_within_T_equals_3(self):
        assert self.d["points_up_within_T"] == 3

    def test_cluster_up_score_v1(self):
        """Legacy count-based: 3 / T."""
        assert self.d["cluster_up_score_v1"] == pytest.approx(3 / T_DEFAULT, abs=1e-6)

    def test_cluster_up_score_active_is_v2(self):
        """Active score uses v2 distance-weighted formula."""
        assert self.d["cluster_up_score"] == pytest.approx(
            self.d["cluster_up_score_v2"], abs=1e-9
        )

    # ── points down ───────────────────────────────────────────────────────

    def test_points_down_within_T_equals_0(self):
        """Team E (15) is far below D (20) — outside threshold."""
        assert self.d["points_down_within_T"] == 0

    def test_cluster_down_risk_is_zero(self):
        assert self.d["cluster_down_risk"] == pytest.approx(0.0, abs=1e-6)

    # ── tier metadata ──────────────────────────────────────────────────────

    def test_tier_idx(self):
        """Team D (20) is the 4th distinct tier (0-indexed: 3)."""
        assert self.d["tier_idx"] == 3

    def test_n_tiers(self):
        """5 teams, 5 distinct PTS values → 5 tiers."""
        assert self.d["n_tiers"] == 5

    # ── best team (Team A) ─────────────────────────────────────────────────

    def test_best_team_no_gains(self):
        a = self.result["Team A"]["PTS/G"]
        assert a["z_to_gain_1"] is None
        assert a["z_to_gain_2"] is None
        assert a["z_to_gain_3"] is None
        assert a["points_up_within_T"] == 0
        assert a["tier_idx"] == 0

    # ── worst team (Team E) ────────────────────────────────────────────────

    def test_worst_team_no_down_risk(self):
        e = self.result["Team E"]["PTS/G"]
        assert e["points_down_within_T"] == 0
        assert e["cluster_down_risk"] == pytest.approx(0.0, abs=1e-6)


# ══════════════════════════════════════════════════════════════════════════════
# TestTieHandling
# ══════════════════════════════════════════════════════════════════════════════

class TestTieHandling:
    """Tied teams must share a tier; z_to_gain_1 must be > 0."""

    @pytest.fixture(autouse=True)
    def _compute(self):
        self.result = compute_cluster_metrics(TIES_FIXTURE)

    def test_bravo_z_to_gain_1_nonzero(self):
        """Bravo (18) tied with Charlie (18) → z to next tier = (20-18)/sigma."""
        bravo = self.result["Bravo"]["PTS/G"]
        assert bravo["z_to_gain_1"] is not None
        assert bravo["z_to_gain_1"] > 0

    def test_charlie_z_to_gain_1_equals_bravo(self):
        """Both tied teams look up to the same higher tier."""
        bravo = self.result["Bravo"]["PTS/G"]
        charlie = self.result["Charlie"]["PTS/G"]
        assert charlie["z_to_gain_1"] == pytest.approx(bravo["z_to_gain_1"], abs=1e-9)

    def test_z_to_gain_1_formula(self):
        """(20 - 18) / sigma_ties."""
        bravo = self.result["Bravo"]["PTS/G"]
        sigma = bravo["sigma"]
        expected = (20.0 - 18.0) / sigma
        assert bravo["z_to_gain_1"] == pytest.approx(expected, abs=1e-6)

    def test_tied_teams_have_same_tier_idx(self):
        bravo = self.result["Bravo"]["PTS/G"]
        charlie = self.result["Charlie"]["PTS/G"]
        assert bravo["tier_idx"] == charlie["tier_idx"]

    def test_n_tiers_deduplicates_ties(self):
        """4 teams but only 3 distinct PTS values → 3 tiers."""
        bravo = self.result["Bravo"]["PTS/G"]
        assert bravo["n_tiers"] == 3

    def test_z_to_gain_2_none_for_second_tier(self):
        """Bravo is in tier 1 (0-indexed) → can only gain 1 more tier."""
        bravo = self.result["Bravo"]["PTS/G"]
        assert bravo["z_to_gain_2"] is None

    def test_best_tied_for_best_is_none(self):
        """Alpha (20) is the sole best tier → no gains possible."""
        alpha = self.result["Alpha"]["PTS/G"]
        assert alpha["z_to_gain_1"] is None
        assert alpha["z_to_gain_2"] is None
        assert alpha["z_to_gain_3"] is None

    def test_worst_team_down_risk_zero(self):
        """Delta (14) at the bottom → no tiers below."""
        delta = self.result["Delta"]["PTS/G"]
        assert delta["points_down_within_T"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# TestEdgeCases
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases: empty input, single team, all-same values, missing value."""

    def test_empty_rows(self):
        assert compute_cluster_metrics([]) == {}

    def test_single_team_all_none(self):
        """With one team, sigma is None → all cluster metrics None."""
        rows = [
            _make_row("Solo", pts=20.0, fg=0.500, ft=0.800, threes=3.0,
                      reb=10.0, ast=8.0, stl=2.0, blk=2.0),
        ]
        result = compute_cluster_metrics(rows)
        for cat_name in ["PTS/G", "FG%", "FT%", "3PM/G", "REB/G", "AST/G", "STL/G", "BLK/G"]:
            entry = result["Solo"][cat_name]
            assert entry["sigma"] is None
            assert entry["z_to_gain_1"] is None
            assert entry["points_up_within_T"] is None
            assert entry["cluster_up_score"] is None

    def test_all_same_value_sigma_none(self):
        """Zero-variance category → sigma None → all metrics None."""
        rows = [
            _make_row("A", pts=15.0),
            _make_row("B", pts=15.0),
            _make_row("C", pts=15.0),
        ]
        result = compute_cluster_metrics(rows)
        for team in ["A", "B", "C"]:
            entry = result[team]["PTS/G"]
            assert entry["sigma"] is None
            assert entry["z_to_gain_1"] is None
            assert entry["points_up_within_T"] is None

    def test_missing_value_returns_none(self):
        """Team with None for a category gets a fully-None metrics entry."""
        rows = [
            _make_row("A", pts=20.0, fg=0.500, ft=0.800, threes=3.0,
                      reb=10.0, ast=8.0, stl=2.0, blk=2.0),
            _make_row("B", pts=18.0, fg=0.480, ft=0.780, threes=2.5,
                      reb=9.0, ast=7.0, stl=1.5, blk=1.5),
            _make_row("C", pts=None, fg=0.460, ft=0.760, threes=2.0,
                      reb=8.0, ast=6.0, stl=1.0, blk=1.0),
        ]
        result = compute_cluster_metrics(rows)
        c_pts = result["C"]["PTS/G"]
        assert c_pts["sigma"] is None
        assert c_pts["z_to_gain_1"] is None
        assert c_pts["z_to_gain_2"] is None
        assert c_pts["points_up_within_T"] is None
        assert c_pts["cluster_up_score"] is None
        assert c_pts["points_down_within_T"] is None
        assert c_pts["cluster_down_risk"] is None

    def test_sigma_is_none_when_only_one_valid_value(self):
        """Sigma requires >= 2 non-None values; with 1, it stays None."""
        rows = [
            _make_row("A", pts=20.0),
            _make_row("B", pts=None),
        ]
        result = compute_cluster_metrics(rows)
        # Both teams should see sigma=None for PTS/G.
        assert result["A"]["PTS/G"]["sigma"] is None
        assert result["B"]["PTS/G"]["sigma"] is None

    def test_two_teams_no_cluster_overlap(self):
        """Two teams far apart: points_up=0 for best, points_down=0 for worst."""
        rows = [
            _make_row("High", pts=100.0, fg=0.600, ft=0.900, threes=5.0,
                      reb=15.0, ast=12.0, stl=3.0, blk=3.0),
            _make_row("Low",  pts=1.0,   fg=0.300, ft=0.500, threes=0.1,
                      reb=1.0,  ast=0.5,  stl=0.1, blk=0.1),
        ]
        result = compute_cluster_metrics(rows)
        high_pts = result["High"]["PTS/G"]
        low_pts = result["Low"]["PTS/G"]

        # High (best): no tiers above
        assert high_pts["points_up_within_T"] == 0
        assert high_pts["z_to_gain_1"] is None

        # Low (worst): no tiers below
        assert low_pts["points_down_within_T"] == 0
        assert low_pts["cluster_down_risk"] == pytest.approx(0.0, abs=1e-9)

    def test_custom_threshold(self):
        """T=0 means nothing is 'within threshold'."""
        rows = CLUSTERED_ABOVE
        result = compute_cluster_metrics(rows, T=0.0001)
        # With a near-zero threshold, nothing except an exact tie passes.
        d = result["Team D"]["PTS/G"]
        # All tiers above D have strictly positive gaps → none within T≈0.
        assert d["points_up_within_T"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# TestClusterScoreFormulas
# ══════════════════════════════════════════════════════════════════════════════

class TestClusterScoreFormulas:
    """Verify v1 count-based and v2 distance-weighted formulas."""

    def test_v1_up_score_formula(self):
        """v1: cluster_up_score_v1 = points_up_within_T / T."""
        result = compute_cluster_metrics(CLUSTERED_ABOVE)
        d = result["Team D"]["PTS/G"]
        expected = d["points_up_within_T"] / T_DEFAULT
        assert d["cluster_up_score_v1"] == pytest.approx(expected, abs=1e-9)

    def test_v1_down_risk_formula(self):
        """v1: cluster_down_risk_v1 = points_down_within_T / T."""
        result = compute_cluster_metrics(CLUSTERED_ABOVE)
        e = result["Team E"]["PTS/G"]
        assert e["cluster_down_risk_v1"] == pytest.approx(0.0, abs=1e-9)

    def test_v2_active_score_not_equal_to_v1(self):
        """Active v2 score differs from v1 when tiers are not equidistant."""
        result = compute_cluster_metrics(CLUSTERED_ABOVE)
        d = result["Team D"]["PTS/G"]
        # Team D has 3 reachable tiers with different z-distances → v2 != v1
        assert d["cluster_up_score_v1"] != pytest.approx(
            d["cluster_up_score_v2"], abs=1e-6
        )
        # Active field should be v2
        assert d["cluster_up_score"] == pytest.approx(
            d["cluster_up_score_v2"], abs=1e-9
        )

    def test_all_teams_have_entries_for_all_categories(self):
        """Every team must have a metrics dict for all 8 categories."""
        cat_names = {"FG%", "FT%", "3PM/G", "PTS/G", "REB/G", "AST/G", "STL/G", "BLK/G"}
        result = compute_cluster_metrics(CLUSTERED_ABOVE)
        for team_name in ["Team A", "Team B", "Team C", "Team D", "Team E"]:
            assert set(result[team_name].keys()) == cat_names


# ══════════════════════════════════════════════════════════════════════════════
# TestClusterTags
# ══════════════════════════════════════════════════════════════════════════════

from fba.analysis.cluster_leverage import N_CLUSTER_TARGETS, N_CLUSTER_DEFEND


class TestClusterTags:
    """TAG assignment: TARGET on highest cluster_up_score, DEFEND on highest cluster_down_risk."""

    @pytest.fixture(autouse=True)
    def _compute(self):
        self.result = compute_cluster_metrics(CLUSTERED_ABOVE)

    def test_tag_field_present_on_all_entries(self):
        """Every entry must have a 'tag' key."""
        for team_name in self.result:
            for cat_name, m in self.result[team_name].items():
                assert "tag" in m, f"Missing 'tag' on {team_name}/{cat_name}"

    def test_target_count_lte_n_targets(self):
        """No team should receive more than N_CLUSTER_TARGETS TARGET tags."""
        for team_name, cats in self.result.items():
            target_count = sum(1 for m in cats.values() if m["tag"] == "TARGET")
            assert target_count <= N_CLUSTER_TARGETS, team_name

    def test_defend_count_lte_n_defend(self):
        """No team should receive more than N_CLUSTER_DEFEND DEFEND tags."""
        for team_name, cats in self.result.items():
            defend_count = sum(1 for m in cats.values() if m["tag"] == "DEFEND")
            assert defend_count <= N_CLUSTER_DEFEND, team_name

    def test_no_overlap_between_target_and_defend(self):
        """A category tagged TARGET must not also be tagged DEFEND."""
        for team_name, cats in self.result.items():
            for cat_name, m in cats.items():
                assert m["tag"] in (None, "TARGET", "DEFEND"), \
                    f"Unexpected tag {m['tag']!r} on {team_name}/{cat_name}"
            target_cats = {n for n, m in cats.items() if m["tag"] == "TARGET"}
            defend_cats = {n for n, m in cats.items() if m["tag"] == "DEFEND"}
            assert target_cats.isdisjoint(defend_cats)

    def test_target_tags_on_highest_cluster_up_scores(self):
        """TARGET cats must be the top N_CLUSTER_TARGETS by cluster_up_score (>0)."""
        for team_name, cats in self.result.items():
            scorable = [
                (cat_name, m["cluster_up_score"])
                for cat_name, m in cats.items()
                if m.get("cluster_up_score") is not None and m["cluster_up_score"] > 0
            ]
            scorable.sort(key=lambda x: (-x[1], x[0]))
            expected_targets = {name for name, _ in scorable[:N_CLUSTER_TARGETS]}
            actual_targets = {n for n, m in cats.items() if m["tag"] == "TARGET"}
            assert actual_targets == expected_targets, team_name

    def test_defend_tags_on_highest_cluster_down_risk_excluding_targets(self):
        """DEFEND cats must be top N_CLUSTER_DEFEND by cluster_down_risk (>0), not TARGET."""
        for team_name, cats in self.result.items():
            target_cats = {n for n, m in cats.items() if m["tag"] == "TARGET"}
            candidates = [
                (cat_name, m["cluster_down_risk"])
                for cat_name, m in cats.items()
                if cat_name not in target_cats
                and m.get("cluster_down_risk") is not None
                and m["cluster_down_risk"] > 0
            ]
            candidates.sort(key=lambda x: (-x[1], x[0]))
            expected_defends = {name for name, _ in candidates[:N_CLUSTER_DEFEND]}
            actual_defends = {n for n, m in cats.items() if m["tag"] == "DEFEND"}
            assert actual_defends == expected_defends, team_name

    def test_zero_score_not_tagged_target(self):
        """Categories with cluster_up_score == 0 must never receive TARGET."""
        for team_name, cats in self.result.items():
            for cat_name, m in cats.items():
                if m.get("cluster_up_score") == 0.0:
                    assert m["tag"] != "TARGET", \
                        f"{team_name}/{cat_name} has score=0 but is tagged TARGET"

    def test_zero_risk_not_tagged_defend(self):
        """Categories with cluster_down_risk == 0 must never receive DEFEND."""
        for team_name, cats in self.result.items():
            for cat_name, m in cats.items():
                if m.get("cluster_down_risk") == 0.0:
                    assert m["tag"] != "DEFEND", \
                        f"{team_name}/{cat_name} has risk=0 but is tagged DEFEND"

    def test_none_score_not_tagged(self):
        """Categories with None scores must never receive any tag."""
        for team_name, cats in self.result.items():
            for cat_name, m in cats.items():
                if m.get("cluster_up_score") is None and m.get("cluster_down_risk") is None:
                    assert m["tag"] is None, \
                        f"{team_name}/{cat_name} has None scores but is tagged {m['tag']!r}"


# ══════════════════════════════════════════════════════════════════════════════
# TestZToLose — downside z-score columns
# ══════════════════════════════════════════════════════════════════════════════

class TestZToLose:
    """
    z_to_lose_k = (x_i - tier_values[tier_idx + k]) / sigma
    Tests use CLUSTERED_ABOVE and TIES_FIXTURE.

    CLUSTERED_ABOVE PTS tiers (descending): [21, 20.5, 20.3, 20, 15]
    sigma ≈ _CLUSTER_SIGMA

    Team D (20, tier_idx=3):
      z_to_lose_1 = (20 - 15) / sigma  [next tier down is 15]
      z_to_lose_2 = None                [no tier at idx 5]
      z_to_lose_3 = None

    Team A (21, tier_idx=0):
      z_to_lose_1 = (21 - 20.5) / sigma
      z_to_lose_2 = (21 - 20.3) / sigma
      z_to_lose_3 = (21 - 20.0) / sigma

    Team E (15, tier_idx=4):
      z_to_lose_1 = None  [no tier below]
    """

    @pytest.fixture(autouse=True)
    def _compute(self):
        self.result = compute_cluster_metrics(CLUSTERED_ABOVE)

    def test_z_to_lose_fields_present(self):
        """Every entry must expose z_to_lose_1/2/3 keys."""
        d = self.result["Team D"]["PTS/G"]
        assert "z_to_lose_1" in d
        assert "z_to_lose_2" in d
        assert "z_to_lose_3" in d

    def test_team_d_z_to_lose_1(self):
        """Team D (20) drops to tier idx 4 (15): z = (20-15)/sigma."""
        d = self.result["Team D"]["PTS/G"]
        sigma = d["sigma"]
        expected = (20.0 - 15.0) / sigma
        assert d["z_to_lose_1"] == pytest.approx(expected, abs=1e-6)

    def test_team_d_z_to_lose_2_none(self):
        """Team D is at tier_idx=3; idx 5 doesn't exist → None."""
        d = self.result["Team D"]["PTS/G"]
        assert d["z_to_lose_2"] is None

    def test_team_d_z_to_lose_3_none(self):
        d = self.result["Team D"]["PTS/G"]
        assert d["z_to_lose_3"] is None

    def test_team_a_z_to_lose_1(self):
        """Team A (21, tier_idx=0) drops to 20.5: z = (21-20.5)/sigma."""
        a = self.result["Team A"]["PTS/G"]
        sigma = a["sigma"]
        expected = (21.0 - 20.5) / sigma
        assert a["z_to_lose_1"] == pytest.approx(expected, abs=1e-6)

    def test_team_a_z_to_lose_2(self):
        """Team A drops 2 tiers to 20.3: z = (21-20.3)/sigma."""
        a = self.result["Team A"]["PTS/G"]
        sigma = a["sigma"]
        expected = (21.0 - 20.3) / sigma
        assert a["z_to_lose_2"] == pytest.approx(expected, abs=1e-6)

    def test_team_a_z_to_lose_3(self):
        """Team A drops 3 tiers to 20.0: z = (21-20.0)/sigma."""
        a = self.result["Team A"]["PTS/G"]
        sigma = a["sigma"]
        expected = (21.0 - 20.0) / sigma
        assert a["z_to_lose_3"] == pytest.approx(expected, abs=1e-6)

    def test_team_e_z_to_lose_1_none(self):
        """Team E is at the bottom tier → no tier below → None."""
        e = self.result["Team E"]["PTS/G"]
        assert e["z_to_lose_1"] is None
        assert e["z_to_lose_2"] is None
        assert e["z_to_lose_3"] is None

    def test_z_to_lose_always_positive(self):
        """All non-None z_to_lose values must be positive (dropping down = positive distance)."""
        for team_name, cats in self.result.items():
            for cat_name, m in cats.items():
                for field in ("z_to_lose_1", "z_to_lose_2", "z_to_lose_3"):
                    val = m.get(field)
                    if val is not None:
                        assert val > 0, f"{team_name}/{cat_name}/{field}={val}"

    def test_z_to_lose_increasing(self):
        """Dropping more tiers requires larger movement: z_to_lose_1 ≤ z_to_lose_2 ≤ z_to_lose_3."""
        a = self.result["Team A"]["PTS/G"]
        assert a["z_to_lose_1"] <= a["z_to_lose_2"]
        assert a["z_to_lose_2"] <= a["z_to_lose_3"]

    def test_none_entry_z_to_lose_all_none(self):
        """Teams with sigma=None should have z_to_lose_1/2/3 as None."""
        rows = [
            _make_row("A", pts=20.0, fg=0.500, ft=0.800, threes=3.0,
                      reb=10.0, ast=8.0, stl=2.0, blk=2.0),
            _make_row("B", pts=None, fg=0.480, ft=0.780, threes=2.5,
                      reb=9.0, ast=7.0, stl=1.5, blk=1.5),
        ]
        result = compute_cluster_metrics(rows)
        # B has no PTS value → sigma is None for that entry
        b_pts = result["B"]["PTS/G"]
        assert b_pts["z_to_lose_1"] is None
        assert b_pts["z_to_lose_2"] is None
        assert b_pts["z_to_lose_3"] is None


# ══════════════════════════════════════════════════════════════════════════════
# TestV2Differentiation — tight vs spread clusters
# ══════════════════════════════════════════════════════════════════════════════

class TestV2Differentiation:
    """v2 distance-weighted scoring differentiates tight vs spread clusters.

    v1 treats [0.10, 0.20, 0.30] and [0.60, 0.70, 0.74] identically (same
    count of reachable tiers). v2 rewards tightness: closer tiers contribute
    more via weight(z) = 1 - z/T.
    """

    def test_weighted_score_tight_beats_spread(self):
        """Direct unit test of _weighted_score."""
        T = 0.75
        tight = [0.10, 0.20, 0.30]
        spread = [0.60, 0.70, 0.74]

        # v1 (count-based) would be identical: 3/T = 4.0 for both
        assert len(tight) / T == pytest.approx(len(spread) / T)

        # v2 must differ: tight > spread
        v2_tight = _weighted_score(tight, T)
        v2_spread = _weighted_score(spread, T)
        assert v2_tight > v2_spread

    def test_weighted_score_values(self):
        """Verify exact v2 formula: Σ(1 - z/T) / T."""
        T = 0.75
        z_list = [0.10, 0.20, 0.30]
        # weights: (1-0.10/0.75)=0.8667, (1-0.20/0.75)=0.7333, (1-0.30/0.75)=0.6
        expected = (0.8667 + 0.7333 + 0.6) / 0.75
        assert _weighted_score(z_list, T) == pytest.approx(expected, abs=1e-3)

    def test_single_tier_at_zero_distance(self):
        """A tier at z=0 (exact tie) gets maximum weight=1.0."""
        T = 0.75
        score = _weighted_score([0.0], T)
        assert score == pytest.approx(1.0 / T, abs=1e-9)

    def test_single_tier_at_threshold(self):
        """A tier at z=T gets weight=0.0 → score=0."""
        T = 0.75
        score = _weighted_score([T], T)
        assert score == pytest.approx(0.0, abs=1e-9)

    def test_empty_list_not_called(self):
        """_weighted_score is only called with non-empty lists; verify result if called."""
        T = 0.75
        # Division by T of an empty sum = 0/T = 0
        score = _weighted_score([], T)
        assert score == pytest.approx(0.0, abs=1e-9)

    def test_diagnostics_populated(self):
        """z_up_max, z_up_mean, z_down_max, z_down_mean should be present."""
        result = compute_cluster_metrics(CLUSTERED_ABOVE)
        d = result["Team D"]["PTS/G"]
        assert d["z_up_max"] is not None
        assert d["z_up_mean"] is not None
        # Team D has 0 tiers below within T → diagnostics are None
        assert d["z_down_max"] is None
        assert d["z_down_mean"] is None

    def test_z_up_mean_correct(self):
        """z_up_mean should be the mean of reachable upside z-distances."""
        result = compute_cluster_metrics(CLUSTERED_ABOVE)
        d = result["Team D"]["PTS/G"]
        sigma = d["sigma"]
        z_vals = [
            (20.3 - 20.0) / sigma,
            (20.5 - 20.0) / sigma,
            (21.0 - 20.0) / sigma,
        ]
        assert d["z_up_mean"] == pytest.approx(sum(z_vals) / len(z_vals), abs=1e-6)
        assert d["z_up_max"] == pytest.approx(max(z_vals), abs=1e-6)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
