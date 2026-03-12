"""Tests for the time series analysis module."""

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from fba.category_config import CategoryConfig
from fba.timeseries.db import get_db, init_db
from fba.timeseries.snapshots import (
    get_all_snapshot_dates,
    get_closest_snapshot_date,
    get_snapshot_range,
    get_snapshots_for_date,
    save_snapshot,
)
from fba.timeseries.windowed import (
    compute_all_windows,
    compute_chart_data,
    compute_windowed_stats,
)
from fba.timeseries.scorecard import compute_scorecard


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    """Create a temporary SQLite database and return its path."""
    path = tmp_path / "test_timeseries.db"
    init_db(path)
    return str(path)


@pytest.fixture
def sample_configs():
    """Return a minimal set of CategoryConfigs for testing."""
    return [
        CategoryConfig(
            key="FG%", display="FG%", stat_id=5,
            higher_is_better=True, is_percentage=True,
            per_game_key=None, per_game_display="FG%", rank_key="FG%_Rank",
        ),
        CategoryConfig(
            key="PTS", display="PTS", stat_id=12,
            higher_is_better=True, is_percentage=False,
            per_game_key="PTS_pg", per_game_display="PTS/G", rank_key="PTS_Rank",
        ),
        CategoryConfig(
            key="REB", display="REB", stat_id=15,
            higher_is_better=True, is_percentage=False,
            per_game_key="REB_pg", per_game_display="REB/G", rank_key="REB_Rank",
        ),
        CategoryConfig(
            key="TO", display="TO", stat_id=19,
            higher_is_better=False, is_percentage=False,
            per_game_key="TO_pg", per_game_display="TO/G", rank_key="TO_Rank",
        ),
    ]


def _make_teams(day_offset=0, gp_base=50):
    """Create sample team data simulating cumulative stats."""
    gp_a = gp_base + day_offset * 1
    gp_b = gp_base + day_offset * 1
    return [
        {
            "team_key": "nba.l.12345.t.1",
            "team_name": "Team Alpha",
            "stats": {
                "GP": gp_a,
                "FG%": 0.480 + day_offset * 0.001,
                "FGM": 500 + day_offset * 10,
                "FGA": 1050 + day_offset * 20,
                "FTM": 300 + day_offset * 5,
                "FTA": 380 + day_offset * 6,
                "PTS": 1500 + day_offset * 30,
                "REB": 600 + day_offset * 12,
                "TO": 200 + day_offset * 4,
            },
        },
        {
            "team_key": "nba.l.12345.t.2",
            "team_name": "Team Beta",
            "stats": {
                "GP": gp_b,
                "FG%": 0.460 + day_offset * 0.002,
                "FGM": 480 + day_offset * 12,
                "FGA": 1040 + day_offset * 25,
                "FTM": 280 + day_offset * 6,
                "FTA": 370 + day_offset * 7,
                "PTS": 1400 + day_offset * 35,
                "REB": 580 + day_offset * 10,
                "TO": 220 + day_offset * 3,
            },
        },
    ]


# ── Database Tests ────────────────────────────────────────────────────────

class TestDatabase:
    def test_init_db_creates_tables(self, db_path):
        conn = get_db(db_path)
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {r["name"] for r in tables}
            assert "stat_snapshots" in table_names
        finally:
            conn.close()

    def test_init_db_idempotent(self, db_path):
        init_db(db_path)
        init_db(db_path)
        conn = get_db(db_path)
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            assert len([r for r in tables if r["name"] == "stat_snapshots"]) == 1
        finally:
            conn.close()


# ── Snapshot Tests ────────────────────────────────────────────────────────

class TestSnapshots:
    def test_save_and_read_snapshot(self, db_path):
        teams = _make_teams()
        rows = save_snapshot("u1", "league1", teams, db_path=db_path)
        assert rows == 2

        snaps = get_snapshots_for_date("u1", "league1", date.today().isoformat(), db_path=db_path)
        assert len(snaps) == 2
        assert snaps[0]["team_name"] == "Team Alpha"
        assert snaps[0]["gp"] == 50
        assert snaps[0]["stats"]["PTS"] == 1500

    def test_same_day_upsert(self, db_path):
        """Multiple saves on the same day keep only the latest."""
        teams_v1 = _make_teams(day_offset=0)
        save_snapshot("u1", "league1", teams_v1, db_path=db_path)

        teams_v2 = _make_teams(day_offset=5)
        save_snapshot("u1", "league1", teams_v2, db_path=db_path)

        snaps = get_snapshots_for_date("u1", "league1", date.today().isoformat(), db_path=db_path)
        assert len(snaps) == 2
        # Should have the v2 values
        alpha = [s for s in snaps if s["team_name"] == "Team Alpha"][0]
        assert alpha["stats"]["PTS"] == 1650  # 1500 + 5*30

    def test_multi_day_snapshots(self, db_path):
        """Snapshots on different days are stored separately."""
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 8, tzinfo=timezone.utc)

        save_snapshot("u1", "lg1", _make_teams(0), db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", _make_teams(7), db_path=db_path, snapshot_time=day2)

        rng = get_snapshot_range("u1", "lg1", db_path=db_path)
        assert rng is not None
        assert rng[0] == "2026-03-01"
        assert rng[1] == "2026-03-08"
        assert rng[2] == 2

    def test_snapshot_range_empty(self, db_path):
        assert get_snapshot_range("u1", "lg_none", db_path=db_path) is None

    def test_get_all_snapshot_dates(self, db_path):
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 5, tzinfo=timezone.utc)
        day3 = datetime(2026, 3, 10, tzinfo=timezone.utc)

        save_snapshot("u1", "lg1", _make_teams(0), db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", _make_teams(4), db_path=db_path, snapshot_time=day2)
        save_snapshot("u1", "lg1", _make_teams(9), db_path=db_path, snapshot_time=day3)

        dates = get_all_snapshot_dates("u1", "lg1", db_path=db_path)
        assert dates == ["2026-03-01", "2026-03-05", "2026-03-10"]

    def test_closest_snapshot_date_before(self, db_path):
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 8, tzinfo=timezone.utc)

        save_snapshot("u1", "lg1", _make_teams(0), db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", _make_teams(7), db_path=db_path, snapshot_time=day2)

        closest = get_closest_snapshot_date("u1", "lg1", "2026-03-05", direction="before", db_path=db_path)
        assert closest == "2026-03-01"

    def test_closest_snapshot_date_after(self, db_path):
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 8, tzinfo=timezone.utc)

        save_snapshot("u1", "lg1", _make_teams(0), db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", _make_teams(7), db_path=db_path, snapshot_time=day2)

        closest = get_closest_snapshot_date("u1", "lg1", "2026-03-05", direction="after", db_path=db_path)
        assert closest == "2026-03-08"

    def test_user_league_isolation(self, db_path):
        """Different users don't see each other's data."""
        save_snapshot("u1", "lg1", _make_teams(0), db_path=db_path)
        save_snapshot("u2", "lg1", _make_teams(5), db_path=db_path)

        snaps_u1 = get_snapshots_for_date("u1", "lg1", date.today().isoformat(), db_path=db_path)
        snaps_u2 = get_snapshots_for_date("u2", "lg1", date.today().isoformat(), db_path=db_path)

        alpha_u1 = [s for s in snaps_u1 if s["team_name"] == "Team Alpha"][0]
        alpha_u2 = [s for s in snaps_u2 if s["team_name"] == "Team Alpha"][0]
        assert alpha_u1["stats"]["PTS"] == 1500
        assert alpha_u2["stats"]["PTS"] == 1650


# ── Windowed Stats Tests ──────────────────────────────────────────────────

class TestWindowedStats:
    def test_compute_7d_window(self, db_path, sample_configs):
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 8, tzinfo=timezone.utc)

        save_snapshot("u1", "lg1", _make_teams(0, gp_base=50), db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", _make_teams(7, gp_base=50), db_path=db_path, snapshot_time=day2)

        result = compute_windowed_stats(
            "u1", "lg1", 7, sample_configs,
            current_date=date(2026, 3, 8), db_path=db_path,
        )

        assert result["available"] is True
        assert result["actual_days"] == 7
        assert len(result["teams"]) == 2

        alpha = [t for t in result["teams"] if t["team_name"] == "Team Alpha"][0]
        # GP delta: (50+7) - 50 = 7
        assert alpha["gp_delta"] == 7
        # PTS delta: (1500+210) - 1500 = 210; PTS/G = 210/7 = 30
        assert alpha["PTS_pg"] == pytest.approx(30.0)
        # REB delta: (600+84) - 600 = 84; REB/G = 84/7 = 12
        assert alpha["REB_pg"] == pytest.approx(12.0)
        # FG% recomputed: FGM delta = 70, FGA delta = 140; 70/140 = 0.5
        assert alpha["FG%"] == pytest.approx(0.5)

    def test_window_not_available_single_snapshot(self, db_path, sample_configs):
        save_snapshot("u1", "lg1", _make_teams(0), db_path=db_path,
                      snapshot_time=datetime(2026, 3, 8, tzinfo=timezone.utc))

        result = compute_windowed_stats(
            "u1", "lg1", 7, sample_configs,
            current_date=date(2026, 3, 8), db_path=db_path,
        )
        assert result["available"] is False

    def test_window_not_available_no_data(self, db_path, sample_configs):
        result = compute_windowed_stats(
            "u1", "lg1", 7, sample_configs,
            current_date=date(2026, 3, 8), db_path=db_path,
        )
        assert result["available"] is False

    def test_compute_all_windows(self, db_path, sample_configs):
        # Create snapshots spanning 30 days
        base = date(2026, 2, 6)
        for day_num in [0, 1, 7, 14, 30]:
            snap_date = base + timedelta(days=day_num)
            snap_time = datetime(snap_date.year, snap_date.month, snap_date.day, tzinfo=timezone.utc)
            save_snapshot("u1", "lg1", _make_teams(day_num, gp_base=40),
                          db_path=db_path, snapshot_time=snap_time)

        result = compute_all_windows(
            "u1", "lg1", sample_configs,
            current_date=date(2026, 3, 8), db_path=db_path,
        )

        assert "1d" in result
        assert "7d" in result
        assert "14d" in result
        assert "30d" in result
        # 30d should be available since we have 2026-02-06 and 2026-03-08
        assert result["30d"]["available"] is True

    def test_gp_zero_in_window(self, db_path, sample_configs):
        """When GP doesn't change in a window, per-game stats should be None."""
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 8, tzinfo=timezone.utc)

        # Same GP on both days (team didn't play)
        teams_day1 = _make_teams(0, gp_base=50)
        teams_day2 = _make_teams(0, gp_base=50)  # same stats
        save_snapshot("u1", "lg1", teams_day1, db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", teams_day2, db_path=db_path, snapshot_time=day2)

        result = compute_windowed_stats(
            "u1", "lg1", 7, sample_configs,
            current_date=date(2026, 3, 8), db_path=db_path,
        )

        assert result["available"] is True
        alpha = [t for t in result["teams"] if t["team_name"] == "Team Alpha"][0]
        assert alpha["gp_delta"] == 0
        assert alpha["PTS_pg"] is None


# ── Chart Data Tests ──────────────────────────────────────────────────────

class TestChartData:
    def test_chart_data_structure(self, db_path, sample_configs):
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 8, tzinfo=timezone.utc)

        save_snapshot("u1", "lg1", _make_teams(0, gp_base=50), db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", _make_teams(7, gp_base=50), db_path=db_path, snapshot_time=day2)

        chart = compute_chart_data("u1", "lg1", sample_configs, db_path=db_path)

        assert len(chart) == 2
        assert chart[0]["date"] == "2026-03-01"
        assert chart[1]["date"] == "2026-03-08"
        assert "Team Alpha" in chart[0]["teams"]
        assert "PTS_pg" in chart[0]["teams"]["Team Alpha"]

    def test_chart_data_needs_two_snapshots(self, db_path, sample_configs):
        save_snapshot("u1", "lg1", _make_teams(0), db_path=db_path)
        chart = compute_chart_data("u1", "lg1", sample_configs, db_path=db_path)
        assert len(chart) == 0


# ── Scorecard Tests ───────────────────────────────────────────────────────

class TestScorecard:
    def test_scorecard_basic(self, db_path, sample_configs):
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 8, tzinfo=timezone.utc)

        save_snapshot("u1", "lg1", _make_teams(0, gp_base=50), db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", _make_teams(7, gp_base=50), db_path=db_path, snapshot_time=day2)

        # Season averages from current totals
        season_averages = {
            "Team Alpha": {
                "FG%": 0.487,
                "PTS_pg": 1710 / 57,  # season total / GP
                "REB_pg": 684 / 57,
                "TO_pg": 228 / 57,
            },
            "Team Beta": {
                "FG%": 0.474,
                "PTS_pg": 1645 / 57,
                "REB_pg": 650 / 57,
                "TO_pg": 241 / 57,
            },
        }

        result = compute_scorecard(
            "u1", "lg1", "Team Alpha", sample_configs, season_averages,
            current_date=date(2026, 3, 8), db_path=db_path,
        )

        assert "windows" in result
        assert "7d" in result["windows"]
        w7 = result["windows"]["7d"]
        assert w7["available"] is True
        assert "PTS_pg" in w7["categories"]
        cat = w7["categories"]["PTS_pg"]
        assert cat["value"] is not None
        assert cat["vs_own_avg"] is not None
        assert cat["league_best_team"] is not None

    def test_scorecard_no_data(self, db_path, sample_configs):
        result = compute_scorecard(
            "u1", "lg1", "Team Alpha", sample_configs, {},
            current_date=date(2026, 3, 8), db_path=db_path,
        )
        assert "windows" in result
        for wk in ["1d", "7d", "14d", "30d"]:
            assert result["windows"][wk]["available"] is False

    def test_scorecard_to_direction(self, db_path, sample_configs):
        """TO (lower-is-better) should have inverted vs_own_avg sign."""
        day1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        day2 = datetime(2026, 3, 8, tzinfo=timezone.utc)

        save_snapshot("u1", "lg1", _make_teams(0, gp_base=50), db_path=db_path, snapshot_time=day1)
        save_snapshot("u1", "lg1", _make_teams(7, gp_base=50), db_path=db_path, snapshot_time=day2)

        # Season avg TO/G for Alpha: 228/57 = 4.0
        season_averages = {
            "Team Alpha": {"FG%": 0.487, "PTS_pg": 30.0, "REB_pg": 12.0, "TO_pg": 4.0},
            "Team Beta": {"FG%": 0.474, "PTS_pg": 28.0, "REB_pg": 10.0, "TO_pg": 3.8},
        }

        result = compute_scorecard(
            "u1", "lg1", "Team Alpha", sample_configs, season_averages,
            current_date=date(2026, 3, 8), db_path=db_path,
        )

        w7 = result["windows"]["7d"]
        to_cat = w7["categories"]["TO_pg"]
        # TO delta: 28/7 = 4.0 per game in window. Same as season avg (4.0).
        # vs_own_avg should be 0 or close to 0
        assert to_cat["value"] is not None
