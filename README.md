# Fantasy Basketball Automation

Local Yahoo Fantasy Basketball standings dashboard with scraping, per-game normalization, and category target analysis.

## Current Status

- Main app: `src/fba/app.py` (Flask, port `8080`)
- Scraper: `src/fba/scraper.py` (Playwright + BeautifulSoup)
- Analysis engine: `src/fba/analysis/category_targets.py`
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
│   │   └── _analysis_key.html
│   └── static/
│       ├── app.js
│       └── style.css
├── scripts/
│   ├── start_server.sh
│   └── run_tests_manual.py
├── tests/
│   ├── test_normalize.py
│   └── test_category_targets.py
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
./scripts/start_server.sh
```

Open `http://localhost:8080`.

## First-Time League Setup

1. Open `http://localhost:8080`.
2. Enter your Yahoo league ID and click `Connect`.
3. If no session exists, a visible browser opens for Yahoo login.
4. After login, session is saved to `data/browser_state.json` and standings are saved to `data/standings.json`.

## Endpoints

- `GET /` Standings dashboard
- `GET /analysis` Category Targets page
- `POST /refresh` Run scraper for configured league ID
- `GET /api/standings` Raw standings JSON
- `GET /api/config` Current config (`league_id`, `has_session`)
- `POST /api/config` Set `league_id`

## Core Behavior Notes

- `normalize.py` ranks categories as `N = best` and `1 = worst`.
- `/analysis` computes per-category gap-to-gain, buffer-to-lose, target score, plus `TARGET` and `DEFEND` tags.
- `webhook_server.py` is not wired into the main app flow.

## Useful Commands

```bash
# Start app
./scripts/start_server.sh

# Manual login + scrape
PYTHONPATH=src python src/fba/scraper.py --login --league-id <LEAGUE_ID>

# Headless scrape using saved session
PYTHONPATH=src python src/fba/scraper.py --league-id <LEAGUE_ID>

# Manual checks
PYTHONPATH=src python scripts/run_tests_manual.py

# Automated tests
./venv/bin/pytest -q
```

## Test Status (Current)

As of February 22, 2026, `./venv/bin/pytest -q` returns:

- `40` passing
- `4` failing (`tests/test_normalize.py` rank-direction expectations)

The failures are in tests only; docs now reflect current implementation behavior (`N=best`).

## Documentation

- Quick setup: `docs/QUICKSTART.md`
- Architecture and flow: `docs/ARCHITECTURE.md`
- Documentation index: `docs/DOCS.md`
- Change log: `docs/CHANGELOG.md`
