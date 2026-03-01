# Architecture Overview

## Runtime Modes

The app has two distinct runtime modes:

- `react` (default): session-driven, OAuth-backed, React UI served from `frontend/dist`
- `legacy`: disk-driven, template-backed, older single-user flow

`auto` is still accepted, but `src/fba/app.py` treats it as `react`.

## React-First Runtime Flow

```text
Browser
  -> GET /, /analysis, /games-played
     -> Flask serves frontend/dist/index.html
  -> React app
     -> GET /api/config, /api/overview, /api/analysis, /api/games-played
     -> POST /api/config (stores league_id in session)
     -> POST /refresh (requires authenticated user)
        -> fba.auth.get_valid_tokens()
        -> fba.yahoo_api.get_oauth_session_from_tokens()
        -> fba.yahoo_api.fetch_standings()
        -> in-memory _standings_cache[league_id]
```

Important details:

- OAuth tokens are stored encrypted in the Flask session cookie.
- The active league ID is stored in the Flask session.
- Refreshed standings are cached in memory only for the running process.
- `POST /refresh` does not write `data/standings.json`.

## Legacy Runtime Flow

```text
Browser
  -> GET /, /analysis, /games-played
     -> Flask renders Jinja templates from src/fba/templates/
     -> load_config() reads data/config.json
     -> load_standings() reads data/standings.json
```

Legacy mode is the only mode that falls back to:

- `data/config.json`
- `data/standings.json`

## Core Backend Modules

### `src/fba/app.py`

- Creates the Flask app and configures Flask-Login.
- Decides whether to serve React or Jinja templates.
- Builds the shared payloads for overview, analysis, and games-played pages.
- Exposes auth endpoints, API endpoints, and React asset serving.
- Uses the current season window for games-played calculations:
  - start: `2025-10-14`
  - end: `2026-03-22`
  - total games default: `816`

### `src/fba/auth.py`

- Builds the Yahoo OAuth authorization URL.
- Exchanges auth codes for tokens.
- Refreshes expired access tokens.
- Encrypts token payloads with Fernet before storing them in the Flask session.
- Integrates with Flask-Login for route protection.

### `src/fba/yahoo_api.py`

- Fetches standings through `yahoo_fantasy_api` instead of scraping HTML.
- Uses direct raw team-stat requests to recover `GP`, which the library omits.
- Computes per-category roto points to match the app's downstream schema.
- Supports two auth styles:
  - file-based `data/oauth2.json`
  - temporary token-based sessions built from web-session tokens

### `src/fba/normalize.py`

- Parses Yahoo stat values.
- Builds per-game rows from raw totals.
- Re-ranks the 8 roto categories using `N = best`, `1 = worst`.
- Produces `rank_total` and `points_delta`.

### `src/fba/analysis/category_targets.py`

- Computes nearest-team gaps up and down.
- Standardizes those gaps by population sigma.
- Calculates `target_score = 1 / z_gap_up + 0.25 * z_gap_down`.
- Assigns `TARGET` to the top 3 scores and `DEFEND` to the 2 lowest non-target buffers.

### `src/fba/analysis/cluster_leverage.py`

- Groups teams into distinct value tiers by category.
- Measures how many tier jumps are reachable inside a `0.75 sigma` effort window.
- Produces `cluster_up_score` and `cluster_down_risk`.
- Applies `TARGET` and `DEFEND` tags using the same 3-and-2 split.

### `src/fba/analysis/games_played.py`

- Computes elapsed days, remaining days, pace so far, pace required, and net delta.
- Returns `date_valid = False` when today's date is outside the selected season window.

## Optional / Legacy Utilities

### `src/fba/scraper.py`

- Uses Playwright + BeautifulSoup to scrape the Yahoo standings page.
- Writes `data/standings.json`.
- Saves browser login state to `data/browser_state.json`.
- Not used by `POST /refresh`.

### `src/fba/oauth_setup.py`

- Bootstraps `data/oauth2.json` for the older file-based Yahoo API flow.
- Useful for CLI/manual fetches, not required for the web app's session-based flow.

### `src/fba/webhook_server.py`

- Separate Flask app from an older Google Sheets integration.
- References scripts not present in this repository.
- Not wired into `src/fba/app.py`.

## Frontend Structure

- `frontend/src/App.tsx`: route map
- `frontend/src/components/AppShell.tsx`: nav, auth state, league controls shell
- `frontend/src/components/LeagueControls.tsx`: connect/refresh flow and 401 redirect handling
- `frontend/src/components/DataTable.tsx`: reusable sortable table
- `frontend/src/pages/OverviewPage.tsx`: standings overview
- `frontend/src/pages/AnalysisPage.tsx`: category targets + cluster leverage
- `frontend/src/pages/GamesPlayedPage.tsx`: season-window controls + games-played pace

## Verification Snapshot

Verified on March 1, 2026:

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`

The full suite is not currently verifiable in the checked-in `venv` until backend dependencies are reinstalled there.
