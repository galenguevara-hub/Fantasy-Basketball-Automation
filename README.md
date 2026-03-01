# Fantasy Basketball Automation

Yahoo Fantasy Basketball analysis app with a Flask backend, a React frontend, Yahoo OAuth login, direct Yahoo Fantasy API refreshes, and three analysis layers:

- per-game normalization and roto re-ranking
- category target scoring
- cluster leverage and games-played pace analysis

## What `main` Runs Today

- `src/fba/app.py`: Flask app on `http://localhost:8080`
- `frontend/`: React + Vite UI, served from `frontend/dist` in default mode
- `src/fba/auth.py`: Yahoo OAuth flow, encrypted token handling, Flask-Login session state
- `src/fba/yahoo_api.py`: direct Yahoo Fantasy API fetches used by `POST /refresh`
- `src/fba/analysis/*.py`: category targets, cluster leverage, and games-played calculations

Legacy/manual utilities still exist, but they are not the default web flow:

- `src/fba/scraper.py`: Playwright scraper that writes `data/standings.json`
- `src/fba/oauth_setup.py`: file-based OAuth bootstrap for `data/oauth2.json`
- `src/fba/webhook_server.py`: older webhook service that references scripts not present in this repo

## Setup

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend install
cp .env.example .env
npm --prefix frontend run build
```

Populate `.env` before using live refresh:

- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `SECRET_KEY` (recommended outside local dev)
- `TOKEN_ENCRYPTION_KEY` (recommended outside local dev)

`YAHOO_REDIRECT_URI` defaults to `http://localhost:8080/auth/yahoo/callback`.

## Run The App

Production-style local run (Flask serves the built React app):

```bash
./scripts/start_server.sh
```

Frontend development (Flask API + Vite dev server together):

```bash
./scripts/start_dev.sh
```

- Flask API: `http://localhost:8080`
- Vite UI: `http://localhost:5173`

Current `vite.config.ts` only proxies `/api` and `/refresh`. If you need the Yahoo login or logout flow during frontend dev, use the Flask-served app on `:8080` or add proxy rules for `/auth` and `/logout`.

## First-Time League Connection

1. Open `http://localhost:8080`.
2. Enter your Yahoo league ID.
3. Click `Connect`.
4. If you are not authenticated, the UI redirects to `/auth/yahoo`.
5. Complete Yahoo OAuth in the browser.
6. The callback stores encrypted Yahoo tokens in the Flask session cookie and returns to the app.
7. The app refreshes standings through the Yahoo Fantasy API and caches them in memory for that league.

There is also a manual fallback endpoint, `POST /auth/code`, for cases where Yahoo shows an authorization code instead of completing the redirect.

## UI Modes

Set `FBA_UI_MODE` before starting Flask:

- `react` (default): serves the React build for `/`, `/analysis`, and `/games-played`; returns `503` if `frontend/dist/index.html` is missing
- `legacy`: serves the older Jinja templates and reads from disk-backed files
- `auto`: accepted for backward compatibility and treated the same as `react`

Examples:

```bash
FBA_UI_MODE=react ./scripts/start_server.sh
FBA_UI_MODE=legacy ./scripts/start_server.sh
```

## Routes

HTML routes:

- `GET /`
- `GET /analysis`
- `GET /games-played`

Auth routes:

- `GET /auth/yahoo`
- `GET /auth/yahoo/callback`
- `POST /auth/code`
- `POST /logout`
- `GET /api/auth/status`

Data routes:

- `GET /api/config`
- `POST /api/config`
- `GET /api/overview`
- `GET /api/analysis`
- `GET /api/games-played`
- `POST /refresh`
- `GET /api/standings`
- `GET /assets/<file>`

## Data And Persistence

React mode is session-driven:

- `session["league_id"]` stores the active league ID
- `session["yahoo_tokens"]` stores encrypted OAuth tokens
- `_standings_cache[league_id]` keeps the latest fetched standings in memory

That means `POST /refresh` does not automatically write `data/standings.json`.

Disk-backed files are still used by legacy/manual paths:

- `data/config.json`: legacy template config fallback
- `data/standings.json`: legacy template data source and scraper output
- `data/oauth2.json`: file-based Yahoo OAuth used by `src/fba/oauth_setup.py` / `src/fba/yahoo_api.py`
- `data/browser_state.json`: Playwright session file used only by `src/fba/scraper.py`

## Useful Commands

```bash
# Start the default app flow
./scripts/start_server.sh

# Start backend + Vite dev server
./scripts/start_dev.sh

# Rebuild the React bundle served by Flask
npm --prefix frontend run build

# Check file-based Yahoo OAuth status (legacy/manual flow)
PYTHONPATH=src ./venv/bin/python -m fba.oauth_setup --check

# Run the legacy Playwright scraper (optional)
./venv/bin/pip install playwright
./venv/bin/playwright install chromium
PYTHONPATH=src ./venv/bin/python src/fba/scraper.py --login --league-id <LEAGUE_ID>

# Run the pure calculation tests
./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py
```

## Verification Snapshot

Verified on March 1, 2026:

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`

The full suite command, `./venv/bin/pytest -q`, currently fails in the checked-in `venv` during collection because required packages such as `python-dotenv` and `flask-login` are not installed there. Re-run `pip install -r requirements.txt` inside `venv` before expecting the full app/API tests to pass.

## Docs

- `docs/QUICKSTART.md`
- `docs/ARCHITECTURE.md`
- `docs/DOCS.md`
- `docs/CHANGELOG.md`
- `docs/IMPLEMENTATION_SUMMARY.md`
- `frontend/README.md`
