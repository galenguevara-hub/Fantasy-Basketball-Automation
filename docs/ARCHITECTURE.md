# Architecture Overview

## Supported Runtime Modes

- `react` (default): session-driven, OAuth-backed, React UI served from
  `frontend/dist`
- `legacy`: disk-driven, template-backed compatibility mode

`auto` is accepted, but `src/fba/app.py` treats it as `react`.

## React Runtime Flow

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

Key points:

- Yahoo tokens are stored encrypted in the Flask session cookie.
- The active league ID is stored in the Flask session.
- Refreshed standings are cached in memory for the running process.
- `POST /refresh` does not write `data/standings.json`.

## Legacy Template Flow

```text
Browser
  -> GET /, /analysis, /games-played
     -> Flask renders Jinja templates
     -> load_config() reads data/config.json
     -> load_standings() reads data/standings.json
```

Legacy mode is the only supported code path that uses:

- `data/config.json`
- `data/standings.json`

## Core Backend Modules

### `src/fba/app.py`

- Creates the Flask app and configures Flask-Login
- Selects React or template rendering
- Builds overview, analysis, and games-played payloads
- Exposes auth routes, API routes, and asset serving

### `src/fba/auth.py`

- Builds the Yahoo OAuth authorization URL
- Exchanges auth codes for tokens
- Refreshes expired access tokens
- Encrypts token payloads before storing them in the session

### `src/fba/yahoo_api.py`

- Fetches standings through `yahoo_fantasy_api`
- Uses raw Yahoo team-stat requests to recover `GP`
- Computes per-category roto points to match the app schema
- Still contains a legacy file-based OAuth fallback for archived tools

### `src/fba/normalize.py`

- Parses Yahoo stat values
- Builds per-game rows from raw totals
- Re-ranks the eight roto categories using `N = best`, `1 = worst`
- Produces `rank_total` and `points_delta`

### `src/fba/analysis/category_targets.py`

- Computes nearest-team gaps up and down
- Standardizes those gaps by population sigma
- Calculates `target_score`
- Assigns `TARGET` and `DEFEND` tags

### `src/fba/analysis/cluster_leverage.py`

- Builds category tiers
- Measures multi-point movement inside a `0.75 sigma` effort window
- Produces `cluster_up_score` and `cluster_down_risk`

### `src/fba/analysis/games_played.py`

- Computes elapsed days, remaining days, pace so far, pace required, and net
  delta
- Returns a `date_valid` flag for out-of-window inputs

## Frontend Structure

- `frontend/src/main.tsx`: app entrypoint
- `frontend/src/App.tsx`: route map
- `frontend/src/components/`: shared UI
- `frontend/src/pages/`: page-level route components
- `frontend/src/lib/`: API and formatting helpers

The frontend is now TypeScript-only. The duplicate `.js` files were removed.

## Archived Material

Deprecated tooling and exploratory scripts were moved to `legacy/`. That
includes:

- the old Playwright scraper
- old file-based OAuth setup helpers
- the removed Google Sheets webhook flow
- exploratory Yahoo API scripts

## Verification Snapshot

Verified on March 1, 2026:

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`
