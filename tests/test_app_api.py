import json
from pathlib import Path

import pytest

from fba import app as app_module

# Module-level store for injecting standings data in tests.
# Monkeypatched into _get_standings so tests don't require Redis or a real user session.
_test_standings: dict = {}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "config.json"
    standings_file = tmp_path / "standings.json"
    frontend_dist_dir = tmp_path / "frontend" / "dist"
    frontend_index_file = frontend_dist_dir / "index.html"

    config_file.write_text(json.dumps({"league_id": "12345"}), encoding="utf-8")

    monkeypatch.setattr(app_module, "CONFIG_FILE", config_file)
    monkeypatch.setattr(app_module, "STANDINGS_FILE", standings_file)
    monkeypatch.setattr(app_module, "FRONTEND_DIST_DIR", frontend_dist_dir)
    monkeypatch.setattr(app_module, "FRONTEND_INDEX_FILE", frontend_index_file)
    monkeypatch.delenv("FBA_UI_MODE", raising=False)

    app_module.app.config["TESTING"] = True
    app_module.app.config["LOGIN_DISABLED"] = True

    # Reset test standings store and patch _get_standings to use it directly,
    # bypassing Redis and current_user authentication checks.
    _test_standings.clear()
    monkeypatch.setattr(app_module, "_get_standings", lambda lid: _test_standings.get(lid))

    test_client = app_module.app.test_client()

    # Set league_id in session (React mode reads from session, not config file)
    with test_client.session_transaction() as sess:
        sess["league_id"] = "12345"

    return test_client, standings_file, frontend_dist_dir


def _load_sample_standings_to_cache():
    """Load sample standings into the test store for league '12345'."""
    _test_standings["12345"] = _sample_standings_payload()


def _sample_standings_payload():
    return {
        "scraped_at": "2026-02-25 11:20:00 AM",
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
                "total_points": 72,
                "stats": {
                    "GP": 120,
                    "FG%": 0.502,
                    "FT%": 0.811,
                    "3PTM": 965,
                    "PTS": 13210,
                    "REB": 5012,
                    "AST": 3021,
                    "ST": 812,
                    "BLK": 541,
                },
                "roto_points": {
                    "FG%": 9,
                    "FT%": 8,
                    "3PTM": 10,
                    "PTS": 9,
                    "REB": 9,
                    "AST": 9,
                    "ST": 9,
                    "BLK": 9,
                },
            },
            {
                "rank": 2,
                "team_name": "Bravo",
                "total_points": 66,
                "stats": {
                    "GP": 118,
                    "FG%": 0.487,
                    "FT%": 0.793,
                    "3PTM": 910,
                    "PTS": 12790,
                    "REB": 4888,
                    "AST": 2899,
                    "ST": 771,
                    "BLK": 498,
                },
                "roto_points": {
                    "FG%": 8,
                    "FT%": 7,
                    "3PTM": 9,
                    "PTS": 8,
                    "REB": 8,
                    "AST": 8,
                    "ST": 9,
                    "BLK": 9,
                },
            },
            {
                "rank": 3,
                "team_name": "Charlie",
                "total_points": 58,
                "stats": {
                    "GP": 119,
                    "FG%": 0.472,
                    "FT%": 0.776,
                    "3PTM": 878,
                    "PTS": 12420,
                    "REB": 4762,
                    "AST": 2750,
                    "ST": 730,
                    "BLK": 460,
                },
                "roto_points": {
                    "FG%": 7,
                    "FT%": 6,
                    "3PTM": 8,
                    "PTS": 7,
                    "REB": 7,
                    "AST": 7,
                    "ST": 7,
                    "BLK": 9,
                },
            },
        ],
    }
    return payload


def test_api_overview_without_data(client):
    test_client, _, _ = client

    response = test_client.get("/api/overview")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["has_data"] is False
    assert payload["league_id"] == "12345"
    assert payload["teams"] == []


def test_api_overview_with_data(client):
    test_client, _, _ = client
    _load_sample_standings_to_cache()

    response = test_client.get("/api/overview")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["has_data"] is True
    assert payload["league_id"] == "12345"
    assert len(payload["teams"]) == 3
    assert len(payload["per_game_rows"]) == 3
    assert len(payload["ranking_rows"]) == 3


def test_api_analysis_supports_team_selection(client):
    test_client, _, _ = client
    _load_sample_standings_to_cache()

    response = test_client.get("/api/analysis?team=Bravo")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["has_data"] is True
    assert payload["selected_team"] == "Bravo"
    assert set(payload["team_names"]) == {"Alpha", "Bravo", "Charlie"}
    assert isinstance(payload["analysis"], list)
    assert isinstance(payload["league_summary"], list)


def test_api_games_played_uses_defaults_for_bad_dates(client):
    test_client, _, _ = client
    _load_sample_standings_to_cache()

    response = test_client.get("/api/games-played?start=bad-date&end=2026-03-22&total_games=0")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["has_data"] is True
    assert payload["start_str"] == "2025-10-14"
    assert payload["end_str"] == "2026-03-22"
    assert payload["total_games"] == 816
    assert "Invalid start date" in payload["date_error"]
    assert len(payload["rows"]) == 3


def test_default_mode_without_build_returns_503(client):
    test_client, _, _ = client

    response = test_client.get("/")
    assert response.status_code == 503
    assert "React build not found" in response.get_data(as_text=True)


def test_react_index_served_when_frontend_build_exists(client):
    test_client, _, frontend_dist_dir = client
    frontend_dist_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dist_dir / "index.html").write_text("<html><body>React Frontend</body></html>", encoding="utf-8")

    for path in ["/", "/analysis", "/games-played"]:
        response = test_client.get(path)
        assert response.status_code == 200
        assert "React Frontend" in response.get_data(as_text=True)


def test_frontend_assets_route(client):
    test_client, _, frontend_dist_dir = client
    assets_dir = frontend_dist_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dist_dir / "index.html").write_text("<html>React Frontend</html>", encoding="utf-8")
    (assets_dir / "main.js").write_text("console.log('ok');", encoding="utf-8")

    response = test_client.get("/assets/main.js")
    assert response.status_code == 200
    assert "console.log('ok');" in response.get_data(as_text=True)


def test_legacy_mode_ignores_react_build(client, monkeypatch: pytest.MonkeyPatch):
    test_client, _, frontend_dist_dir = client
    frontend_dist_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dist_dir / "index.html").write_text("<html><body>React Frontend</body></html>", encoding="utf-8")
    monkeypatch.setenv("FBA_UI_MODE", "legacy")

    response = test_client.get("/")
    assert response.status_code == 200
    assert "Roto Fantasy Basketball Solver" in response.get_data(as_text=True)


def test_legacy_mode_without_build_uses_legacy_templates(client, monkeypatch: pytest.MonkeyPatch):
    test_client, _, _ = client
    monkeypatch.setenv("FBA_UI_MODE", "legacy")

    response = test_client.get("/")
    assert response.status_code == 200
    assert "Roto Fantasy Basketball Solver" in response.get_data(as_text=True)


def test_auto_mode_without_build_returns_503(client, monkeypatch: pytest.MonkeyPatch):
    test_client, _, _ = client
    monkeypatch.setenv("FBA_UI_MODE", "auto")

    response = test_client.get("/")
    assert response.status_code == 503
    assert "React build not found" in response.get_data(as_text=True)


def test_react_mode_without_build_returns_503(client, monkeypatch: pytest.MonkeyPatch):
    test_client, _, _ = client
    monkeypatch.setenv("FBA_UI_MODE", "react")

    response = test_client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    assert "React build not found" in body
