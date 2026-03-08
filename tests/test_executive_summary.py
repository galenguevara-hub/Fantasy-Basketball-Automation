from datetime import date

from fba.analysis.executive_summary import build_executive_summary


SEASON_START = date(2025, 10, 14)
SEASON_END = date(2026, 3, 22)
TODAY = date(2026, 2, 1)


def _team(
    name: str,
    rank: int,
    total_points: float,
    gp: int,
    fg: float,
    ft: float,
    threes: int,
    pts: int,
    reb: int,
    ast: int,
    stl: int,
    blk: int,
) -> dict:
    return {
        "team_name": name,
        "rank": rank,
        "total_points": total_points,
        "stats": {
            "GP": gp,
            "FG%": fg,
            "FT%": ft,
            "3PTM": threes,
            "PTS": pts,
            "REB": reb,
            "AST": ast,
            "ST": stl,
            "BLK": blk,
        },
        "roto_points": {
            "FG%": 3,
            "FT%": 3,
            "3PTM": 3,
            "PTS": 3,
            "REB": 3,
            "AST": 3,
            "ST": 3,
            "BLK": 3,
        },
    }


def _sample_teams() -> list[dict]:
    return [
        _team("Alpha", 1, 68.0, 600, 0.500, 0.810, 900, 12800, 4800, 2900, 760, 500),
        _team("Bravo", 2, 62.0, 580, 0.488, 0.790, 860, 12350, 4700, 2750, 730, 460),
        _team("Charlie", 3, 58.0, 570, 0.474, 0.775, 820, 11980, 4550, 2640, 700, 430),
    ]


def test_build_executive_summary_basic_shape():
    payload = build_executive_summary(
        teams=_sample_teams(),
        selected_team="Bravo",
        start_date=SEASON_START,
        end_date=SEASON_END,
        today_date=TODAY,
        total_games=816,
    )

    assert payload["selected_team"] == "Bravo"
    assert set(payload["team_names"]) == {"Alpha", "Bravo", "Charlie"}
    assert len(payload["per_game_vs_raw_rows"]) == 3
    assert isinstance(payload["summary_card"], dict)
    assert isinstance(payload["actionable_insights"], list)
    assert payload["games_pace"]["max_allowed_games"] == 816
    assert payload["projected_finish"] is not None


def test_build_executive_summary_invalid_team_defaults_to_first():
    payload = build_executive_summary(
        teams=_sample_teams(),
        selected_team="Not A Team",
        start_date=SEASON_START,
        end_date=SEASON_END,
        today_date=TODAY,
        total_games=816,
    )

    assert payload["selected_team"] == "Alpha"
    assert payload["summary_card"]["standings_line"]


def test_build_executive_summary_empty_teams():
    payload = build_executive_summary(
        teams=[],
        selected_team=None,
        start_date=SEASON_START,
        end_date=SEASON_END,
        today_date=TODAY,
        total_games=816,
    )

    assert payload["team_names"] == []
    assert payload["selected_team"] is None
    assert payload["per_game_vs_raw_rows"] == []
    assert payload["actionable_insights"] == []
