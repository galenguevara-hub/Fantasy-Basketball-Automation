# Fantasy Basketball Automation

Local Yahoo Fantasy Basketball standings dashboard with scraping, per-game normalization, category target analysis, cluster leverage analysis, and games-played pace analysis. Includes legacy Flask templates and a React frontend (`frontend/`) backed by JSON APIs.

## Current Status

- Main app: `src/fba/app.py` (Flask, port `8080`)
- Frontend build serving: controlled by `FBA_UI_MODE` (`react`, `legacy`, `auto`; default `react`)
- Scraper: `src/fba/scraper.py` (Playwright + BeautifulSoup)
- Analysis engine:
  - `src/fba/analysis/category_targets.py`
  - `src/fba/analysis/cluster_leverage.py`
  - `src/fba/analysis/games_played.py`
- Runtime data: `data/standings.json`, `data/browser_state.json`, `data/config.json`
- Optional legacy module: `src/fba/webhook_server.py` (references old scripts that are not present)

## Project Layout

```text
Fantasy Basketball Automation/
├── src/fba/
│   ├── app.py
│   ├── scraper.py
│   ├── normalize.py
│   ├── analysis/category_targets.py
│   ├── webhook_server.py
│   ├── templates/
│   │   ├── index.html
│   │   ├── analysis.html
│   │   ├── games_played.html
│   │   └── _analysis_key.html
│   └── static/
│       ├── app.js
│       └── style.css
├── scripts/
│   ├── start_server.sh
│   ├── start_dev.sh
│   └── run_tests_manual.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── pages/
│       └── lib/
├── tests/
│   ├── test_normalize.py
│   ├── test_category_targets.py
│   ├── test_cluster_leverage.py
│   ├── test_games_played.py
│   ├── test_app_api.py
│   └── test_calculation_regression_parity.py
├── data/
│   ├── standings.json
│   ├── standings.csv
│   ├── browser_state.json
│   └── config.json
├── config/
│   ├── oauth2.json
│   └── google_credentials.json
├── docs/
├── requirements.txt
├── oauth2.json.example
└── google_credentials.json.example
```

## Quick Start

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
npm --prefix frontend install
npm --prefix frontend run build
./scripts/start_server.sh
```

Open `http://localhost:8080`.

## React Frontend Development

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation/frontend"
npm install
npm run dev
```

Vite runs on `http://localhost:5173` and proxies API requests to Flask on `http://localhost:8080`.

To run both backend and frontend together:

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
./scripts/start_dev.sh
```

To build and serve React from Flask:

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation/frontend"
npm run build
cd ..
./scripts/start_server.sh
```

### UI Mode Switch

Set `FBA_UI_MODE` before starting Flask:

- `react` (default): always serve React routes; returns `503` if build artifacts are missing.
- `legacy`: compatibility mode that serves Jinja templates.
- `auto`: compatibility alias for `react` (no legacy fallback).

Examples:

```bash
FBA_UI_MODE=react ./scripts/start_server.sh
FBA_UI_MODE=legacy ./scripts/start_server.sh
```

## First-Time League Setup

1. Open `http://localhost:8080`.
2. Enter your Yahoo league ID and click `Connect`.
3. If no session exists, a visible browser opens for Yahoo login.
4. After login, session is saved to `data/browser_state.json` and standings are saved to `data/standings.json`.

## Endpoints

- `GET /` Standings dashboard
- `GET /analysis` Category Targets page
- `GET /games-played` Games played pace page
- `POST /refresh` Run scraper for configured league ID
- `GET /api/standings` Raw standings JSON
- `GET /api/config` Current config (`league_id`, `has_session`)
- `POST /api/config` Set `league_id`
- `GET /api/overview` React-ready standings payload
- `GET /api/analysis` React-ready category analysis payload (`team` query optional)
- `GET /api/games-played` React-ready games played payload (`start`, `end`, `total_games` query optional)
- `GET /assets/<file>` React build assets when `frontend/dist` exists

## Core Behavior Notes

- `normalize.py` ranks categories as `N = best` and `1 = worst`.
- `/analysis` computes per-category gap-to-gain, buffer-to-lose, target score, plus `TARGET` and `DEFEND` tags.
- `/analysis` also computes cluster leverage metrics (`Up Score`, `Dn Risk`) via `cluster_leverage.py`.
- `/games-played` computes pace metrics from date window + total games via `games_played.py`.
- React defaults:
  - Per-Game Category Rankings table: sorted by `Total` descending.
  - Category Analysis table: sorted by `Score` descending.
  - Cluster Leverage table: sorted by `Up Score` descending.
- React URL state:
  - Selected analysis team is tracked with `?team=<TEAM_NAME>`.
  - Games-played filters are tracked with `?start=YYYY-MM-DD&end=YYYY-MM-DD&total_games=<N>`.
- `webhook_server.py` is not wired into the main app flow.

## Useful Commands

```bash
# Start app (React mode, default)
./scripts/start_server.sh

# Start app with legacy templates fallback
FBA_UI_MODE=legacy ./scripts/start_server.sh

# Manual login + scrape
PYTHONPATH=src python src/fba/scraper.py --login --league-id <LEAGUE_ID>

# Headless scrape using saved session
PYTHONPATH=src python src/fba/scraper.py --league-id <LEAGUE_ID>

# Manual checks
PYTHONPATH=src python scripts/run_tests_manual.py

# Automated tests
./venv/bin/pytest -q

# React frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Test Status (Current)

As of February 27, 2026, `./venv/bin/pytest -q` returns `135 passed`.
This includes `tests/test_calculation_regression_parity.py`, which validates legacy-route payloads and React/API payloads produce matching calculated values.

## Documentation

- Quick setup: `docs/QUICKSTART.md`
- Architecture and flow: `docs/ARCHITECTURE.md`
- Documentation index: `docs/DOCS.md`
- Change log: `docs/CHANGELOG.md`
