# Implementation Summary

Status: current as of February 27, 2026.

## What is implemented

- Web app server in `src/fba/app.py`.
- Yahoo standings scraper in `src/fba/scraper.py`.
- Per-game normalization in `src/fba/normalize.py`.
- Category target analysis in `src/fba/analysis/category_targets.py`.
- Cluster leverage analysis in `src/fba/analysis/cluster_leverage.py`.
- Games-played pace analysis in `src/fba/analysis/games_played.py`.
- Legacy template UI in `src/fba/templates/` + `src/fba/static/`.
- React UI in `frontend/` with API-backed pages for standings, category analysis, and games played.

## Active endpoints (`src/fba/app.py`)

- `GET /`
- `GET /analysis`
- `GET /games-played`
- `POST /refresh`
- `GET /api/standings`
- `GET /api/config`
- `POST /api/config`
- `GET /api/overview`
- `GET /api/analysis`
- `GET /api/games-played`
- `GET /assets/<path:filename>`

## Runtime/UI behavior

- UI mode switch via `FBA_UI_MODE`:
  - `react` (default)
  - `legacy`
  - `auto` (alias of `react`)
- Rankings from `normalize.py` use `N=best`, `1=worst`.
- React defaults:
  - Per-Game Category Rankings sorted by `Total` descending.
  - Category Analysis sorted by `Score` descending.
  - Cluster Leverage sorted by `Up Score` descending.
- React query-state:
  - `/analysis?team=<name>`
  - `/games-played?start=<date>&end=<date>&total_games=<n>`
- `refresh` triggers `src/fba/scraper.py` via subprocess.
- If saved session is missing, refresh launches Yahoo login flow.

## Regression and test status

- `./venv/bin/pytest -q` returns `135 passed`.
- Coverage includes parity verification between legacy routes and API/React payloads:
  - `tests/test_calculation_regression_parity.py`
