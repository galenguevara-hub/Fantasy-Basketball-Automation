#!/usr/bin/env python3
"""
Unit tests for category_config module.

Tests cover:
- Building config from raw Yahoo settings
- Building config from legacy display_name lists
- Serialization round-trip
- Default 8-cat config correctness
- Directionality (higher_is_better) handling
- Helper functions (get_counting_configs, get_percentage_configs, etc.)
"""

import pytest

from fba.category_config import (
    CategoryConfig,
    DEFAULT_8CAT_CONFIG,
    KNOWN_STATS,
    _build_single_config,
    build_category_config_from_raw,
    build_category_config_from_list,
    build_stat_id_map,
    get_counting_configs,
    get_percentage_configs,
    get_analysis_keys,
    to_serializable,
    from_serializable,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

YAHOO_8CAT_RAW_SETTINGS = {
    "fantasy_content": {
        "league": [{
            "settings": [{
                "stat_categories": {
                    "stats": {
                        "stat": [
                            {"stat_id": 0, "display_name": "GP", "is_only_display_stat": "1"},
                            {"stat_id": 2, "display_name": "FGA", "is_only_display_stat": "1"},
                            {"stat_id": 3, "display_name": "FGM", "is_only_display_stat": "1"},
                            {"stat_id": 5, "display_name": "FG%", "sort_order": "1"},
                            {"stat_id": 6, "display_name": "FTA", "is_only_display_stat": "1"},
                            {"stat_id": 7, "display_name": "FTM", "is_only_display_stat": "1"},
                            {"stat_id": 8, "display_name": "FT%", "sort_order": "1"},
                            {"stat_id": 10, "display_name": "3PTM", "sort_order": "1"},
                            {"stat_id": 12, "display_name": "PTS", "sort_order": "1"},
                            {"stat_id": 15, "display_name": "REB", "sort_order": "1"},
                            {"stat_id": 16, "display_name": "AST", "sort_order": "1"},
                            {"stat_id": 17, "display_name": "ST", "sort_order": "1"},
                            {"stat_id": 18, "display_name": "BLK", "sort_order": "1"},
                        ]
                    }
                }
            }]
        }]
    }
}

YAHOO_9CAT_RAW_SETTINGS = {
    "fantasy_content": {
        "league": [{
            "settings": [{
                "stat_categories": {
                    "stats": {
                        "stat": [
                            {"stat_id": 0, "display_name": "GP", "is_only_display_stat": "1"},
                            {"stat_id": 5, "display_name": "FG%", "sort_order": "1"},
                            {"stat_id": 8, "display_name": "FT%", "sort_order": "1"},
                            {"stat_id": 10, "display_name": "3PTM", "sort_order": "1"},
                            {"stat_id": 12, "display_name": "PTS", "sort_order": "1"},
                            {"stat_id": 15, "display_name": "REB", "sort_order": "1"},
                            {"stat_id": 16, "display_name": "AST", "sort_order": "1"},
                            {"stat_id": 17, "display_name": "ST", "sort_order": "1"},
                            {"stat_id": 18, "display_name": "BLK", "sort_order": "1"},
                            {"stat_id": 19, "display_name": "TO", "sort_order": "0"},
                        ]
                    }
                }
            }]
        }]
    }
}


# ── Tests: _build_single_config ──────────────────────────────────────────────

class TestBuildSingleConfig:
    """Test the _build_single_config helper."""

    def test_known_counting_stat(self):
        """Build config for a known counting stat (PTS)."""
        config = _build_single_config(12, "PTS")
        assert config is not None
        assert config.key == "PTS"
        assert config.display == "PTS"
        assert config.stat_id == 12
        assert config.higher_is_better is True
        assert config.is_percentage is False
        assert config.per_game_key == "PTS_pg"
        assert config.per_game_display == "PTS/G"
        assert config.rank_key == "PTS_Rank"

    def test_known_percentage_stat(self):
        """Build config for a known percentage stat (FG%)."""
        config = _build_single_config(5, "FG%")
        assert config is not None
        assert config.key == "FG%"
        assert config.is_percentage is True
        assert config.per_game_key is None
        assert config.per_game_display == "FG%"

    def test_display_only_stat_returns_none(self):
        """Display-only stats (GP) return None."""
        config = _build_single_config(0, "GP")
        assert config is None

    def test_turnovers_lower_is_better(self):
        """TO defaults to higher_is_better=False from KNOWN_STATS."""
        config = _build_single_config(19, "TO")
        assert config is not None
        assert config.key == "TO"
        assert config.higher_is_better is False
        assert config.per_game_key == "TO_pg"

    def test_sort_order_overrides_known(self):
        """Yahoo sort_order='0' overrides KNOWN_STATS higher_is_better."""
        # PTS normally has higher_is_better=True, but sort_order=0 forces False
        config = _build_single_config(12, "PTS", sort_order="0")
        assert config is not None
        assert config.higher_is_better is False

    def test_sort_order_1_means_higher_is_better(self):
        """Yahoo sort_order='1' means higher is better."""
        config = _build_single_config(19, "TO", sort_order="1")
        assert config is not None
        assert config.higher_is_better is True  # overridden by sort_order

    def test_unknown_stat_id(self):
        """Unknown stat_id produces a fallback config."""
        config = _build_single_config(999, "Custom Stat")
        assert config is not None
        assert config.key == "STAT_999"
        assert config.display == "Custom Stat"
        assert config.higher_is_better is True  # default
        assert config.is_percentage is False
        assert config.per_game_key == "STAT_999_pg"

    def test_3ptm_display_name(self):
        """3PTM stat uses '3PM' as display name."""
        config = _build_single_config(10, "3PTM")
        assert config is not None
        assert config.key == "3PTM"
        assert config.display == "3PM"
        assert config.per_game_key == "3PTM_pg"
        assert config.per_game_display == "3PM/G"


# ── Tests: build_category_config_from_raw ─────────────────────────────────────

class TestBuildFromRaw:
    """Test parsing Yahoo raw settings."""

    def test_8cat_settings(self):
        """Parse standard 8-cat settings."""
        configs = build_category_config_from_raw(YAHOO_8CAT_RAW_SETTINGS)
        assert len(configs) == 8
        keys = [c.key for c in configs]
        assert "FG%" in keys
        assert "FT%" in keys
        assert "3PTM" in keys
        assert "PTS" in keys
        assert "REB" in keys
        assert "AST" in keys
        assert "ST" in keys
        assert "BLK" in keys
        # GP and display-only stats should be excluded
        assert "GP" not in keys
        assert "FGA" not in keys

    def test_9cat_settings_with_to(self):
        """Parse 9-cat settings with TO (lower-is-better)."""
        configs = build_category_config_from_raw(YAHOO_9CAT_RAW_SETTINGS)
        assert len(configs) == 9
        to_config = [c for c in configs if c.key == "TO"][0]
        assert to_config.higher_is_better is False
        assert to_config.display == "TO"
        assert to_config.per_game_key == "TO_pg"

    def test_all_8cat_higher_is_better(self):
        """All standard 8-cat categories are higher-is-better."""
        configs = build_category_config_from_raw(YAHOO_8CAT_RAW_SETTINGS)
        for c in configs:
            assert c.higher_is_better is True, f"{c.key} should be higher_is_better"

    def test_empty_settings(self):
        """Empty settings produce empty config."""
        configs = build_category_config_from_raw({})
        assert configs == []


# ── Tests: build_category_config_from_list ────────────────────────────────────

class TestBuildFromList:
    """Test legacy display_name list parsing."""

    def test_known_display_names(self):
        """Build config from display_name list."""
        categories = [
            {"display_name": "FG%"},
            {"display_name": "FT%"},
            {"display_name": "3PM"},
            {"display_name": "PTS"},
        ]
        configs = build_category_config_from_list(categories)
        assert len(configs) == 4
        assert configs[0].key == "FG%"
        assert configs[2].key == "3PTM"  # "3PM" display maps to "3PTM" key

    def test_unknown_display_name_skipped(self):
        """Unknown display names are skipped."""
        categories = [
            {"display_name": "PTS"},
            {"display_name": "UNKNOWN_CAT"},
        ]
        configs = build_category_config_from_list(categories)
        assert len(configs) == 1

    def test_empty_list(self):
        """Empty list produces empty config."""
        configs = build_category_config_from_list([])
        assert configs == []


# ── Tests: Serialization ─────────────────────────────────────────────────────

class TestSerialization:
    """Test serialization/deserialization round-trip."""

    def test_round_trip(self):
        """Serialize and deserialize produces equivalent configs."""
        original = DEFAULT_8CAT_CONFIG
        serialized = to_serializable(original)
        restored = from_serializable(serialized)

        assert len(restored) == len(original)
        for orig, rest in zip(original, restored):
            assert orig.key == rest.key
            assert orig.display == rest.display
            assert orig.stat_id == rest.stat_id
            assert orig.higher_is_better == rest.higher_is_better
            assert orig.is_percentage == rest.is_percentage
            assert orig.per_game_key == rest.per_game_key
            assert orig.per_game_display == rest.per_game_display
            assert orig.rank_key == rest.rank_key

    def test_serialized_format(self):
        """Serialized config is a list of plain dicts."""
        serialized = to_serializable(DEFAULT_8CAT_CONFIG[:1])
        assert isinstance(serialized, list)
        assert isinstance(serialized[0], dict)
        assert "key" in serialized[0]
        assert "stat_id" in serialized[0]

    def test_deserialize_legacy_format(self):
        """Deserialize from legacy display_name format."""
        legacy = [
            {"display_name": "FG%"},
            {"display_name": "PTS"},
        ]
        configs = from_serializable(legacy)
        assert len(configs) == 2
        assert configs[0].key == "FG%"
        assert configs[1].key == "PTS"

    def test_deserialize_empty(self):
        """Deserialize empty list."""
        configs = from_serializable([])
        assert configs == []


# ── Tests: Helper functions ───────────────────────────────────────────────────

class TestHelpers:
    """Test helper/filter functions."""

    def test_get_counting_configs(self):
        """Counting configs exclude percentages."""
        counting = get_counting_configs(DEFAULT_8CAT_CONFIG)
        for c in counting:
            assert c.is_percentage is False
        assert len(counting) == 6  # 3PTM, PTS, REB, AST, ST, BLK

    def test_get_percentage_configs(self):
        """Percentage configs include only percentages."""
        pcts = get_percentage_configs(DEFAULT_8CAT_CONFIG)
        for c in pcts:
            assert c.is_percentage is True
        assert len(pcts) == 2  # FG%, FT%

    def test_build_stat_id_map(self):
        """Build stat_id -> config mapping."""
        id_map = build_stat_id_map(DEFAULT_8CAT_CONFIG)
        assert 5 in id_map  # FG%
        assert 12 in id_map  # PTS
        assert id_map[12].key == "PTS"

    def test_get_analysis_keys(self):
        """Analysis keys use per-game keys for counting, raw keys for pcts."""
        keys = get_analysis_keys(DEFAULT_8CAT_CONFIG)
        assert len(keys) == 8

        # Find PTS entry — should use per_game_key
        pts_entry = [k for k in keys if k["key"] == "PTS_pg"][0]
        assert pts_entry["name"] == "PTS/G"
        assert pts_entry["higher_is_better"] is True

        # Find FG% entry — should use raw key
        fg_entry = [k for k in keys if k["key"] == "FG%"][0]
        assert fg_entry["name"] == "FG%"


# ── Tests: DEFAULT_8CAT_CONFIG ────────────────────────────────────────────────

class TestDefault8CatConfig:
    """Test the DEFAULT_8CAT_CONFIG constant."""

    def test_has_8_categories(self):
        """Default config has exactly 8 categories."""
        assert len(DEFAULT_8CAT_CONFIG) == 8

    def test_expected_keys(self):
        """Default config has the expected category keys."""
        keys = {c.key for c in DEFAULT_8CAT_CONFIG}
        expected = {"FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK"}
        assert keys == expected

    def test_all_higher_is_better(self):
        """All 8 default categories are higher-is-better."""
        for c in DEFAULT_8CAT_CONFIG:
            assert c.higher_is_better is True

    def test_percentages_identified(self):
        """FG% and FT% are percentage categories."""
        pct_keys = {c.key for c in DEFAULT_8CAT_CONFIG if c.is_percentage}
        assert pct_keys == {"FG%", "FT%"}


# ── Tests: 9-cat with TO directionality ───────────────────────────────────────

class TestNineCatDirectionality:
    """Test that 9-cat config with TO handles directionality correctly."""

    @pytest.fixture
    def nine_cat_config(self):
        return build_category_config_from_raw(YAHOO_9CAT_RAW_SETTINGS)

    def test_to_is_lower_is_better(self, nine_cat_config):
        """TO has higher_is_better=False in 9-cat config."""
        to_config = [c for c in nine_cat_config if c.key == "TO"][0]
        assert to_config.higher_is_better is False

    def test_to_per_game_key(self, nine_cat_config):
        """TO has correct per-game key."""
        to_config = [c for c in nine_cat_config if c.key == "TO"][0]
        assert to_config.per_game_key == "TO_pg"
        assert to_config.per_game_display == "TO/G"

    def test_to_rank_key(self, nine_cat_config):
        """TO has correct rank key."""
        to_config = [c for c in nine_cat_config if c.key == "TO"][0]
        assert to_config.rank_key == "TO_Rank"

    def test_analysis_keys_include_to(self, nine_cat_config):
        """Analysis keys include TO with correct directionality."""
        keys = get_analysis_keys(nine_cat_config)
        to_entry = [k for k in keys if k["key"] == "TO_pg"][0]
        assert to_entry["higher_is_better"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
