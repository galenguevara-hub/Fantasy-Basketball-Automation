import json
from datetime import date
from pathlib import Path

import pytest

from fba import app as app_module
from fba.analysis.category_targets import RISK_WEIGHT, TIE_SCORE_CAP, compute_category_sigma
from fba.analysis.cluster_leverage import compute_cluster_metrics
from fba.normalize import normalize_standings


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 2, 27)


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value.replace(",", "").strip())
    raise TypeError(f"Unsupported numeric type: {type(value)!r}")


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _write_sample_standings(path: Path):
    payload = {
        "scraped_at": "2026-02-27 08:15:00 AM",
        "league": {
            "categories": [
                {"display_name": "FG%"},
                {"display_name": "FT%"},
                {"display_name": "3PM"},
                {"display_name": "PTS"},
                {"display_name": "REB"},
                {"display_name": "AST"},
                {"display_name": "STL"},
                {"display_name": "BLK"},
            ]
        },
        "teams": [
            {
                "rank": 1,
                "team_name": "Alpha",
                "total_points": 72.5,
                "stats": {
                    "GP": "120",
                    "FG%": "0.501",
                    "FT%": 0.807,
                    "3PTM": "980",
                    "PTS": "13320",
                    "REB": 5040,
                    "AST": "3055",
                    "ST": 825,
                    "BLK": "545",
                },
                "roto_points": {
                    "FG%": 9.5,
                    "FT%": 8.5,
                    "3PTM": 10,
                    "PTS": 9,
                    "REB": 9,
                    "AST": 9,
                    "ST": 9,
                    "BLK": 8.5,
                },
            },
            {
                "rank": 2,
                "team_name": "Bravo",
                "total_points": 68.0,
                "stats": {
                    "GP": 118,
                    "FG%": 0.489,
                    "FT%": 0.798,
                    "3PTM": 935,
                    "PTS": 12840,
                    "REB": 4910,
                    "AST": 2915,
                    "ST": 780,
                    "BLK": 510,
                },
                "roto_points": {
                    "FG%": 8,
                    "FT%": 8,
                    "3PTM": 9,
                    "PTS": 8.5,
                    "REB": 8,
                    "AST": 8,
                    "ST": 8.5,
                    "BLK": 8,
                },
            },
            {
                "rank": 3,
                "team_name": "Charlie",
                "total_points": 63.5,
                "stats": {
                    "GP": 119,
                    "FG%": 0.478,
                    "FT%": 0.785,
                    "3PTM": 900,
                    "PTS": 12490,
                    "REB": 4800,
                    "AST": 2810,
                    "ST": 748,
                    "BLK": 476,
                },
                "roto_points": {
                    "FG%": 7.5,
                    "FT%": 7,
                    "3PTM": 8,
                    "PTS": 8,
                    "REB": 7.5,
                    "AST": 7,
                    "ST": 7.5,
                    "BLK": 8.5,
                },
            },
            {
                "rank": 4,
                "team_name": "Delta",
                "total_points": 59.0,
                "stats": {
                    "GP": 117,
                    "FG%": 0.469,
                    "FT%": 0.772,
                    "3PTM": 865,
                    "PTS": 12120,
                    "REB": 4680,
                    "AST": 2725,
                    "ST": 710,
                    "BLK": 452,
                },
                "roto_points": {
                    "FG%": 6,
                    "FT%": 6,
                    "3PTM": 7,
                    "PTS": 7,
                    "REB": 7,
                    "AST": 6.5,
                    "ST": 6.5,
                    "BLK": 7,
                },
            },
            {
                "rank": 5,
                "team_name": "Echo",
                "total_points": 51.0,
                "stats": {
                    "GP": 116,
                    "FG%": 0.461,
                    "FT%": 0.761,
                    "3PTM": 830,
                    "PTS": 11730,
                    "REB": 4555,
                    "AST": 2610,
                    "ST": 680,
                    "BLK": 420,
                },
                "roto_points": {
                    "FG%": 5,
                    "FT%": 5.5,
                    "3PTM": 6,
                    "PTS": 6.5,
                    "REB": 6.5,
                    "AST": 6,
                    "ST": 6,
                    "BLK": 5.5,
                },
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def regression_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "config.json"
    standings_file = tmp_path / "standings.json"
    frontend_dist_dir = tmp_path / "frontend" / "dist"
    frontend_index_file = frontend_dist_dir / "index.html"

    config_file.write_text(json.dumps({"league_id": "88888"}), encoding="utf-8")

    monkeypatch.setattr(app_module, "CONFIG_FILE", config_file)
    monkeypatch.setattr(app_module, "STANDINGS_FILE", standings_file)
    monkeypatch.setattr(app_module, "FRONTEND_DIST_DIR", frontend_dist_dir)
    monkeypatch.setattr(app_module, "FRONTEND_INDEX_FILE", frontend_index_file)
    monkeypatch.setattr(app_module, "date", FixedDate)
    monkeypatch.setenv("FBA_UI_MODE", "legacy")

    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), standings_file


def test_legacy_payloads_match_api_payloads_for_all_calculated_fields(
    regression_client,
    monkeypatch: pytest.MonkeyPatch,
):
    test_client, standings_file = regression_client
    _write_sample_standings(standings_file)

    def fake_render_template(template_name: str, **kwargs):
        return app_module.jsonify({"template": template_name, "payload": kwargs})

    monkeypatch.setattr(app_module, "render_template", fake_render_template)

    legacy_overview = test_client.get("/").get_json()["payload"]
    api_overview = test_client.get("/api/overview").get_json()
    assert legacy_overview == api_overview

    legacy_analysis = test_client.get("/analysis?team=Charlie").get_json()["payload"]
    api_analysis = test_client.get("/api/analysis?team=Charlie").get_json()
    assert legacy_analysis == api_analysis

    query = "?start=2025-10-14&end=2026-03-22&total_games=816"
    legacy_games = test_client.get(f"/games-played{query}").get_json()["payload"]
    api_games = test_client.get(f"/api/games-played{query}").get_json()
    assert legacy_games == api_games


def test_overview_fields_follow_expected_calculations(regression_client):
    test_client, standings_file = regression_client
    _write_sample_standings(standings_file)

    payload = test_client.get("/api/overview").get_json()
    assert payload["has_data"] is True

    normalized = normalize_standings(payload["teams"])
    assert payload["per_game_rows"] == normalized["per_game_rows"]
    assert payload["ranking_rows"] == normalized["ranking_rows"]

    teams_by_name = {team["team_name"]: team for team in payload["teams"]}
    for row in payload["per_game_rows"]:
        team = teams_by_name[row["team_name"]]
        gp = int(_to_float(team["stats"]["GP"]))

        assert row["GP"] == gp
        assert row["FG%"] == pytest.approx(_to_float(team["stats"]["FG%"]), abs=1e-12)
        assert row["FT%"] == pytest.approx(_to_float(team["stats"]["FT%"]), abs=1e-12)
        assert row["3PM_pg"] == pytest.approx(_to_float(team["stats"]["3PTM"]) / gp, abs=1e-12)
        assert row["PTS_pg"] == pytest.approx(_to_float(team["stats"]["PTS"]) / gp, abs=1e-12)
        assert row["REB_pg"] == pytest.approx(_to_float(team["stats"]["REB"]) / gp, abs=1e-12)
        assert row["AST_pg"] == pytest.approx(_to_float(team["stats"]["AST"]) / gp, abs=1e-12)
        assert row["ST_pg"] == pytest.approx(_to_float(team["stats"]["ST"]) / gp, abs=1e-12)
        assert row["BLK_pg"] == pytest.approx(_to_float(team["stats"]["BLK"]) / gp, abs=1e-12)

    for row in payload["ranking_rows"]:
        cat_ranks = [
            row["FG%_Rank"],
            row["FT%_Rank"],
            row["3PM_Rank"],
            row["PTS_Rank"],
            row["REB_Rank"],
            row["AST_Rank"],
            row["ST_Rank"],
            row["BLK_Rank"],
        ]
        assert row["rank_total"] == sum(cat_ranks)
        assert row["points_delta"] == pytest.approx(row["rank_total"] - row["total_points"], abs=1e-12)


def test_analysis_and_cluster_fields_follow_expected_calculations(regression_client):
    test_client, standings_file = regression_client
    _write_sample_standings(standings_file)

    overview = test_client.get("/api/overview").get_json()
    analysis_payload = test_client.get("/api/analysis?team=Charlie").get_json()

    per_game_rows = overview["per_game_rows"]
    sigmas = compute_category_sigma(per_game_rows)
    all_cluster = compute_cluster_metrics(per_game_rows)

    for row in analysis_payload["analysis"]:
        key = row["key"]
        sigma = sigmas[key]
        value = row["value"]

        if row["next_better_value"] is None:
            assert row["gap_up"] is None
            assert row["z_gap_up"] is None
        else:
            assert row["gap_up"] == pytest.approx(row["next_better_value"] - value, abs=1e-12)
            if sigma is None:
                assert row["z_gap_up"] is None
            else:
                assert row["z_gap_up"] == pytest.approx(row["gap_up"] / sigma, abs=1e-12)

        if row["next_worse_value"] is None:
            assert row["gap_down"] is None
            assert row["z_gap_down"] is None
        else:
            assert row["gap_down"] == pytest.approx(value - row["next_worse_value"], abs=1e-12)
            if sigma is None:
                assert row["z_gap_down"] is None
            else:
                assert row["z_gap_down"] == pytest.approx(row["gap_down"] / sigma, abs=1e-12)

        z_up = row["z_gap_up"]
        z_down = row["z_gap_down"] if row["z_gap_down"] is not None else 0.0
        if z_up is None:
            assert row["target_score"] is None
        else:
            effort = TIE_SCORE_CAP if z_up == 0 else 1.0 / z_up
            expected = effort + RISK_WEIGHT * z_down
            assert row["target_score"] == pytest.approx(expected, abs=1e-12)

    selected_team = analysis_payload["selected_team"]
    selected_cluster = analysis_payload["team_cluster"]
    for category_name, metrics in selected_cluster.items():
        expected = all_cluster[selected_team][category_name]
        assert metrics == expected
        if metrics["cluster_up_score"] is not None:
            assert metrics["cluster_up_score"] == pytest.approx(
                metrics["points_up_within_T"] / metrics["T"],
                abs=1e-12,
            )
        if metrics["cluster_down_risk"] is not None:
            assert metrics["cluster_down_risk"] == pytest.approx(
                metrics["points_down_within_T"] / metrics["T"],
                abs=1e-12,
            )

    ranking_rows = overview["ranking_rows"]
    valid = [row for row in ranking_rows if row["rank_total"] is not None]
    valid.sort(key=lambda row: (-row["rank_total"], row["team_name"]))
    expected_pg_rank = {
        row["team_name"]: _ordinal(index + 1)
        for index, row in enumerate(valid)
    }
    assert analysis_payload["team_pg_rank"] == expected_pg_rank

    for row in analysis_payload["league_summary"]:
        targets = row["targets"]
        assert targets == sorted(targets, key=lambda item: -(item["target_score"] or 0))

        defends = row["defends"]
        assert defends == sorted(defends, key=lambda item: -(item["target_score"] or 0))

        team_cluster = all_cluster[row["team_name"]]
        expected_cluster_targets = sorted(
            [cat for cat, m in team_cluster.items() if m.get("tag") == "TARGET"],
            key=lambda cat: -(team_cluster[cat].get("cluster_up_score") or 0),
        )
        expected_cluster_defends = sorted(
            [cat for cat, m in team_cluster.items() if m.get("tag") == "DEFEND"],
            key=lambda cat: -(team_cluster[cat].get("cluster_down_risk") or 0),
        )

        assert row["cluster_targets"] == expected_cluster_targets
        assert row["cluster_defends"] == expected_cluster_defends


def test_games_played_fields_follow_expected_calculations(regression_client):
    test_client, standings_file = regression_client
    _write_sample_standings(standings_file)

    payload = test_client.get("/api/games-played?start=2025-10-14&end=2026-03-22&total_games=816").get_json()
    overview = test_client.get("/api/overview").get_json()
    rank_total_by_team = {row["team_name"]: row["rank_total"] for row in overview["ranking_rows"]}

    assert payload["date_valid"] is True
    elapsed = payload["elapsed_days"]
    remaining = payload["remaining_days"]
    assert elapsed == 137
    assert remaining == 24

    for row in payload["rows"]:
        gp = row["gp"]
        assert row["rank_total"] == rank_total_by_team[row["team_name"]]

        if gp is None:
            assert row["avg_gp_per_day_so_far"] is None
            assert row["avg_gp_per_day_needed"] is None
            assert row["net_rate_delta"] is None
            continue

        expected_remaining_games = payload["total_games"] - gp
        expected_so_far = gp / elapsed
        expected_needed = expected_remaining_games / remaining
        expected_delta = expected_needed - expected_so_far

        assert row["games_remaining"] == expected_remaining_games
        assert row["avg_gp_per_day_so_far"] == pytest.approx(expected_so_far, abs=1e-12)
        assert row["avg_gp_per_day_needed"] == pytest.approx(expected_needed, abs=1e-12)
        assert row["net_rate_delta"] == pytest.approx(expected_delta, abs=1e-12)
