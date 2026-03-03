# Architecture Overview

## Branch Snapshot

As of March 3, 2026:

- `main` and `feat/saas-dev` include the Docker + Fly.io deployment work
- `saas` and `deploy/railway` stop before those deployment changes

This document describes the latest local `main` branch state.

## Supported Runtime Modes

- `react` (default): session-driven, OAuth-backed, React UI served from
  `frontend/dist`
- `legacy`: disk-driven, template-backed compatibility mode

`auto` is accepted, but `src/fba/app.py` treats it as `react`.

## Local Shell Runtime Flow

```text
Browser
  -> GET /, /analysis, /games-played
     -> Flask serves frontend/dist/index.html
  -> React app
     -> GET /api/config, /api/overview, /api/analysis, /api/games-played
     -> POST /api/config
     -> POST /refresh
        -> fba.auth.get_valid_tokens()
        -> fba.yahoo_api.get_oauth_session_from_tokens()
        -> fba.yahoo_api.fetch_standings()
        -> cache result
```

## Session And Cache Behavior

### Without `REDIS_URL`

- Flask uses cookie-based sessions
- the app still starts
- but refreshed standings are not persisted for the React API flow because the
  current refresh path only writes to Redis

### With `REDIS_URL`

- Flask-Session stores sessions in Redis
- standings are cached in Redis with keys scoped by `user_id + league_id`
- cached standings use a 1-hour TTL
- this is the intended production path for Docker/Fly.io
- this is also the only fully working persistence path for the current React
  refresh flow

## Docker Runtime

`Dockerfile` is now a two-stage build:

1. `node:20-alpine`
   Builds the React frontend
2. `python:3.11-slim`
   Installs Python dependencies and runs the app with Gunicorn

Production container details:

- `PYTHONPATH=/app/src`
- `FBA_UI_MODE=react`
- non-root runtime user: `fba`
- exposed port: `8080`
- Gunicorn command:
  - 2 workers
  - 120-second timeout
  - stdout/stderr logging enabled

`.dockerignore` excludes local data, secrets, tests, docs, scripts, and git
metadata from the image.

## Docker Compose Topology

`docker-compose.yml` defines:

- `redis`
  - `redis:7-alpine`
  - local port `6379`
  - named volume `redis_data`
  - health check via `redis-cli ping`
- `app`
  - built from `Dockerfile`
  - local port `8080`
  - depends on healthy Redis

Compose wires these runtime variables:

- `REDIS_URL=redis://redis:6379/0`
- `YAHOO_REDIRECT_URI=http://localhost:8080/auth/yahoo/callback`
- `FBA_UI_MODE=react`

## Fly.io Topology

`fly.toml` defines the current hosted deployment shape:

- app: `roto-fantasy-solver`
- region: `ord`
- build source: `Dockerfile`
- internal port: `8080`
- HTTPS enforced
- machine auto-stop/auto-start enabled
- minimum running machines: `0`
- health check: `GET /api/auth/status`

Fly deploys the same Docker image used locally. Redis must be supplied
externally through `REDIS_URL`.

## Core Backend Modules

### `src/fba/app.py`

- creates the Flask app
- conditionally enables Redis-backed Flask-Session
- selects React or template rendering
- builds overview, analysis, and games-played payloads
- reads the cache from Redis when available
- writes refreshed standings to Redis when available

### `src/fba/auth.py`

- builds the Yahoo OAuth authorization URL
- exchanges auth codes for tokens
- refreshes expired access tokens
- encrypts token payloads before storing them in the session

### `src/fba/yahoo_api.py`

- fetches standings through `yahoo_fantasy_api`
- uses raw Yahoo team-stat requests to recover `GP`
- computes per-category roto points to match the app schema
- still contains a legacy file-based OAuth fallback for archived tools

### `src/fba/normalize.py`

- parses Yahoo stat values
- builds per-game rows from raw totals
- re-ranks the eight roto categories using `N = best`, `1 = worst`
- produces `rank_total` and `points_delta`

### `src/fba/analysis/category_targets.py`

- computes nearest-team gaps up and down
- standardizes those gaps by population sigma
- calculates `target_score`
- assigns `TARGET` and `DEFEND` tags

### `src/fba/analysis/cluster_leverage.py`

- builds category tiers
- measures multi-point movement inside a `0.75 sigma` effort window
- produces `cluster_up_score` and `cluster_down_risk`

### `src/fba/analysis/games_played.py`

- computes elapsed days, remaining days, pace so far, pace required, and net
  delta
- returns a `date_valid` flag for out-of-window inputs

## Frontend Structure

- `frontend/src/main.tsx`: app entrypoint
- `frontend/src/App.tsx`: route map
- `frontend/src/components/`: shared UI
- `frontend/src/pages/`: page-level route components
- `frontend/src/lib/`: API and formatting helpers

The frontend is TypeScript-only. The duplicate `.js` files were removed before
the Docker/Fly deployment work landed.

## Legacy Material

Deprecated tooling and exploratory scripts were moved to `legacy/`. That
includes:

- the old Playwright scraper
- old file-based OAuth setup helpers
- the removed Google Sheets webhook flow
- exploratory Yahoo API scripts

## Verification Snapshot

Verified on March 3, 2026:

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`
- `npm --prefix frontend run build`
- Result: passed

Not fully verified:

- no live Docker build/run
- no live Fly deploy
