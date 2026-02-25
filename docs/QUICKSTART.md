# Quick Start

## 1) Install

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 2) Start the App

```bash
./scripts/start_server.sh
```

Open `http://localhost:8080`.

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
```

## Files You Will See Updated

- `data/config.json` stores `league_id`
- `data/browser_state.json` stores Playwright session
- `data/standings.json` stores latest scraped standings
