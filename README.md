# Fantasy Basketball Automation

Yahoo Fantasy Basketball analysis app with a Flask backend, a React frontend,
Yahoo OAuth login, and direct Yahoo Fantasy API refreshes.

## Supported App Path

The supported runtime path is:

- `src/fba/app.py`
- `src/fba/auth.py`
- `src/fba/yahoo_api.py`
- `src/fba/normalize.py`
- `src/fba/analysis/`
- `frontend/`

Archived one-off tooling, exploratory scripts, and deprecated flows now live in
`legacy/`.

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

Set these in `.env` before using live refresh:

- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `SECRET_KEY`

Recommended outside throwaway local use:

- `TOKEN_ENCRYPTION_KEY`

`YAHOO_REDIRECT_URI` defaults to `http://localhost:8080/auth/yahoo/callback`.

## Run

Default local run:

```bash
./scripts/start_server.sh
```

Frontend development:

```bash
./scripts/start_dev.sh
```

- Flask API: `http://localhost:8080`
- Vite UI: `http://localhost:5173`

`vite.config.ts` proxies `/api`, `/refresh`, `/auth`, and `/logout` to the
Flask backend during frontend development.

## First-Time League Connection

1. Open `http://localhost:8080`.
2. Enter your Yahoo league ID.
3. Click `Connect`.
4. If you are not authenticated, the UI redirects to `/auth/yahoo`.
5. Complete Yahoo OAuth.
6. The app refreshes standings through the Yahoo Fantasy API and caches them in
   memory for the current session.

If Yahoo returns an authorization code instead of redirecting cleanly, use the
manual fallback handled by `POST /auth/code`.

## UI Modes

- `react` (default): serves the built React UI and returns `503` if the build
  is missing
- `legacy`: serves the older Jinja templates backed by disk files
- `auto`: accepted for backward compatibility and treated as `react`

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
- `session["yahoo_tokens"]` stores encrypted Yahoo tokens
- `_standings_cache[league_id]` stores refreshed standings in memory

That means `POST /refresh` does not write `data/standings.json`.

Legacy template mode still reads:

- `data/config.json`
- `data/standings.json`

## Archived Material

Deprecated utilities and exploratory files have been moved to `legacy/`,
including:

- old Playwright scraping helpers
- old file-based OAuth bootstrap helpers
- the removed Google Sheets webhook flow
- exploratory Yahoo API scripts
- the old manual test runner

Nothing under `legacy/` is required for the current app.

## Useful Commands

```bash
# Start the supported app flow
./scripts/start_server.sh

# Start backend + Vite dev server
./scripts/start_dev.sh

# Rebuild the React bundle served by Flask
npm --prefix frontend run build

# Run the maintained calculation tests
./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py
```

## Verification Snapshot

Verified on March 1, 2026:

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`

The full suite command, `./venv/bin/pytest -q`, still fails in the checked-in
`venv` during collection because backend packages such as `python-dotenv` and
`flask-login` are missing there.

## Docs

- `docs/QUICKSTART.md`
- `docs/ARCHITECTURE.md`
- `docs/DOCS.md`
- `docs/CHANGELOG.md`
- `docs/IMPLEMENTATION_SUMMARY.md`
- `frontend/README.md`
- `legacy/README.md`
