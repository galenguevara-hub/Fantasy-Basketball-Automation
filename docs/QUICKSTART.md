# Quick Start

## 1) Install

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
npm --prefix frontend install
npm --prefix frontend run build
```

## 2) Start the App

```bash
./scripts/start_server.sh
```

Open `http://localhost:8080`.

To run the original mainline templates:

```bash
FBA_UI_MODE=legacy ./scripts/start_server.sh
```

## 2b) React Frontend Dev Mode (Optional)

```bash
./scripts/start_dev.sh
```

This starts:
- React app: `http://localhost:5173`
- Flask API: `http://localhost:8080`

## 2c) Serve React Build From Flask

```bash
cd frontend
npm run build
cd ..
./scripts/start_server.sh
```

By default (`FBA_UI_MODE=react`), Flask serves React at `/`, `/analysis`, and `/games-played`.

## 2d) Select UI Mode (Optional)

```bash
# Force React routes (errors with 503 if build is missing)
FBA_UI_MODE=react ./scripts/start_server.sh

# Force legacy Jinja templates
FBA_UI_MODE=legacy ./scripts/start_server.sh
```

`FBA_UI_MODE=auto` is supported as a compatibility alias and behaves like `react`.

## React UI Defaults

- `/` Per-Game Category Rankings defaults to `Total` descending.
- `/analysis` Category Analysis defaults to `Score` descending.
- `/analysis` Cluster Leverage defaults to `Up Score` descending.
- `/analysis` team selection is reflected in `?team=...`.
- `/games-played` filter state is reflected in `?start=...&end=...&total_games=...`.

## 3) Connect a League

1. Enter Yahoo league ID in the top input.
2. Click `Connect`.
3. If session is missing, a browser opens for Yahoo login.
4. After login, standings are scraped automatically.

## Common Commands

```bash
# Start app
./scripts/start_server.sh

# Scrape with login window (first time or re-auth)
PYTHONPATH=src python src/fba/scraper.py --login --league-id <LEAGUE_ID>

# Scrape headless with saved session
PYTHONPATH=src python src/fba/scraper.py --league-id <LEAGUE_ID>

# Run manual script checks
PYTHONPATH=src python scripts/run_tests_manual.py

# Run pytest
./venv/bin/pytest -q

# Run calculation parity regression checks only
./venv/bin/pytest -q tests/test_calculation_regression_parity.py
```

## Files You Will See Updated

- `data/config.json` stores `league_id`
- `data/browser_state.json` stores Playwright session
- `data/standings.json` stores latest scraped standings
