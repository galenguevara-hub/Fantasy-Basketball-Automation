"""
Dynamic League Category Configuration

Single source of truth for scoring category metadata. Built from Yahoo API
league settings so the app supports any category set (8-cat, 9-cat, etc.)
without hard-coding.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

import objectpath


# Yahoo stat_id → known metadata for NBA fantasy categories.
# This is a reference lookup; the dynamic config is built from Yahoo settings.
KNOWN_STATS: dict[int, dict[str, Any]] = {
    0:  {"key": "GP",   "display": "GP",   "higher_is_better": True,  "is_percentage": False, "is_display_only": True},
    2:  {"key": "FGA",  "display": "FGA",  "higher_is_better": True,  "is_percentage": False, "is_display_only": True},
    3:  {"key": "FGM",  "display": "FGM",  "higher_is_better": True,  "is_percentage": False, "is_display_only": True},
    5:  {"key": "FG%",  "display": "FG%",  "higher_is_better": True,  "is_percentage": True},
    6:  {"key": "FTA",  "display": "FTA",  "higher_is_better": True,  "is_percentage": False, "is_display_only": True},
    7:  {"key": "FTM",  "display": "FTM",  "higher_is_better": True,  "is_percentage": False, "is_display_only": True},
    8:  {"key": "FT%",  "display": "FT%",  "higher_is_better": True,  "is_percentage": True},
    10: {"key": "3PTM", "display": "3PM",  "higher_is_better": True,  "is_percentage": False},
    11: {"key": "3PT%", "display": "3PT%", "higher_is_better": True,  "is_percentage": True},
    12: {"key": "PTS",  "display": "PTS",  "higher_is_better": True,  "is_percentage": False},
    15: {"key": "REB",  "display": "REB",  "higher_is_better": True,  "is_percentage": False},
    16: {"key": "AST",  "display": "AST",  "higher_is_better": True,  "is_percentage": False},
    17: {"key": "ST",   "display": "STL",  "higher_is_better": True,  "is_percentage": False},
    18: {"key": "BLK",  "display": "BLK",  "higher_is_better": True,  "is_percentage": False},
    19: {"key": "TO",   "display": "TO",   "higher_is_better": False, "is_percentage": False},
}


@dataclass
class CategoryConfig:
    """Metadata for a single league scoring category."""

    key: str                        # Canonical backend key: "FG%", "3PTM", "TO"
    display: str                    # Frontend display label: "FG%", "3PM", "TO"
    stat_id: int                    # Yahoo stat_id
    higher_is_better: bool          # False for TO
    is_percentage: bool             # True for FG%, FT%
    per_game_key: Optional[str]     # "PTS_pg" for counting stats, None for percentages
    per_game_display: str           # "PTS/G" or "FG%" (same as display for pcts)
    rank_key: str                   # "PTS_Rank", "FG%_Rank", etc.


def _build_single_config(stat_id: int, display_name: str, sort_order: Optional[str] = None) -> Optional[CategoryConfig]:
    """Build a CategoryConfig for one stat entry from Yahoo settings.

    Args:
        stat_id: Yahoo numeric stat identifier.
        display_name: Yahoo display_name from settings.
        sort_order: Yahoo sort_order ("0" = ascending/lower-is-better, "1" = descending/higher-is-better).

    Returns:
        CategoryConfig or None if this is a display-only stat (e.g., GP).
    """
    known = KNOWN_STATS.get(stat_id, {})

    # Skip display-only stats (GP, FGA, FGM, etc.)
    if known.get("is_display_only"):
        return None

    key = known.get("key", f"STAT_{stat_id}")
    display = known.get("display", display_name)
    is_percentage = known.get("is_percentage", False)

    # Directionality: Yahoo sort_order > KNOWN_STATS > default (higher-is-better)
    if sort_order is not None:
        higher_is_better = sort_order != "0"
    else:
        higher_is_better = known.get("higher_is_better", True)

    # Per-game key: counting stats get "_pg" suffix, percentages stay as-is
    if is_percentage:
        per_game_key = None
        per_game_display = display
    else:
        per_game_key = f"{key}_pg"
        per_game_display = f"{display}/G"

    rank_key = f"{key}_Rank"

    return CategoryConfig(
        key=key,
        display=display,
        stat_id=stat_id,
        higher_is_better=higher_is_better,
        is_percentage=is_percentage,
        per_game_key=per_game_key,
        per_game_display=per_game_display,
        rank_key=rank_key,
    )


def build_category_config_from_raw(raw_settings: dict) -> list[CategoryConfig]:
    """Build category config list from Yahoo raw league settings JSON.

    Parses ``$..stat_categories..stat`` from the raw settings to extract
    stat_id, display_name, and sort_order for each scoring category.

    Args:
        raw_settings: JSON response from ``league.yhandler.get_settings_raw()``.

    Returns:
        List of CategoryConfig for each active scoring category.
    """
    tree = objectpath.Tree(raw_settings)
    stats = list(tree.execute("$..stat_categories..stat"))

    configs: list[CategoryConfig] = []
    for stat in stats:
        # Skip display-only stats (Yahoo marks them)
        if "is_only_display_stat" in stat:
            continue

        stat_id = int(stat.get("stat_id", -1))
        display_name = stat.get("display_name", f"Stat {stat_id}")
        sort_order = stat.get("sort_order")

        config = _build_single_config(stat_id, display_name, sort_order)
        if config is not None:
            configs.append(config)

    return configs


def build_category_config_from_list(categories: list[dict]) -> list[CategoryConfig]:
    """Build category config from a simple list of category dicts.

    This handles the legacy format: ``[{"display_name": "FG%"}, ...]``
    by matching display names to KNOWN_STATS.

    Args:
        categories: List of dicts with at least ``display_name``.

    Returns:
        List of CategoryConfig for matched categories.
    """
    # Build reverse lookup: display_name -> (stat_id, known_meta)
    display_to_stat: dict[str, tuple[int, dict]] = {}
    for sid, meta in KNOWN_STATS.items():
        display_to_stat[meta["display"]] = (sid, meta)
        # Also map by key for cases where display_name matches key
        display_to_stat[meta["key"]] = (sid, meta)

    configs: list[CategoryConfig] = []
    for cat in categories:
        name = cat.get("display_name", "")
        match = display_to_stat.get(name)
        if match is not None:
            sid, _ = match
            config = _build_single_config(sid, name)
            if config is not None:
                configs.append(config)

    return configs


def build_stat_id_map(configs: list[CategoryConfig]) -> dict[int, CategoryConfig]:
    """Return {stat_id: CategoryConfig} for stat ingestion filtering."""
    return {c.stat_id: c for c in configs}


def get_counting_configs(configs: list[CategoryConfig]) -> list[CategoryConfig]:
    """Return only non-percentage (counting) category configs."""
    return [c for c in configs if not c.is_percentage]


def get_percentage_configs(configs: list[CategoryConfig]) -> list[CategoryConfig]:
    """Return only percentage category configs."""
    return [c for c in configs if c.is_percentage]


def get_analysis_keys(configs: list[CategoryConfig]) -> list[dict[str, str]]:
    """Return category metadata in the format used by analysis modules.

    Each entry has: name, key (per-game key for counting, raw key for pct),
    display (per-game display label), higher_is_better.
    """
    result = []
    for c in configs:
        result.append({
            "name": c.per_game_display,
            "key": c.per_game_key if c.per_game_key else c.key,
            "display": c.per_game_display,
            "higher_is_better": c.higher_is_better,
        })
    return result


def to_serializable(configs: list[CategoryConfig]) -> list[dict[str, Any]]:
    """Serialize config list for JSON storage in standings data."""
    return [asdict(c) for c in configs]


def from_serializable(data: list[dict[str, Any]]) -> list[CategoryConfig]:
    """Deserialize config list from JSON standings data.

    Handles both the new full format and the legacy ``{"display_name": ...}`` format.
    """
    if not data:
        return []

    # Check if this is the new format (has 'key' field) or legacy format
    first = data[0]
    if "key" in first and "stat_id" in first:
        # New format — full CategoryConfig dicts
        return [CategoryConfig(**d) for d in data]

    # Legacy format — just display_name dicts
    return build_category_config_from_list(data)


# ── Default 8-category config (fallback for old data) ──────────────────────

DEFAULT_8CAT_CONFIG: list[CategoryConfig] = [
    _build_single_config(sid, KNOWN_STATS[sid]["display"])  # type: ignore[arg-type]
    for sid in (5, 8, 10, 12, 15, 16, 17, 18)
    if _build_single_config(sid, KNOWN_STATS[sid]["display"]) is not None
]
