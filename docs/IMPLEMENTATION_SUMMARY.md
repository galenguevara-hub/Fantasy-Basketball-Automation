# Implementation Summary

Status: current as of March 3, 2026.

## What Is Implemented

- Flask web app in `src/fba/app.py`
- React UI in `frontend/`
- Legacy Jinja UI in `src/fba/templates/`
- Yahoo OAuth web login and encrypted session token storage in `src/fba/auth.py`
- Direct Yahoo Fantasy API refresh path in `src/fba/yahoo_api.py`
- Per-game normalization in `src/fba/normalize.py`
- Category target analysis in `src/fba/analysis/category_targets.py`
- Cluster leverage analysis in `src/fba/analysis/cluster_leverage.py`
- Games-played pace analysis in `src/fba/analysis/games_played.py`
- Multi-stage Docker build in `Dockerfile`
- Local Docker + Redis stack in `docker-compose.yml`
- Fly.io deployment definition in `fly.toml`
- Redis-backed sessions and per-user standings cache when `REDIS_URL` is set

## Active Endpoints (`src/fba/app.py`)

- `GET /`
- `GET /analysis`
- `GET /games-played`
- `GET /auth/yahoo`
- `GET /auth/yahoo/callback`
- `POST /auth/code`
- `POST /logout`
- `GET /api/auth/status`
- `GET /api/config`
- `POST /api/config`
- `GET /api/overview`
- `GET /api/analysis`
- `GET /api/games-played`
- `POST /refresh`
- `GET /api/standings`
- `GET /assets/<path:filename>`

## Runtime Notes

- Default mode is `FBA_UI_MODE=react`
- `react` and `auto` require `frontend/dist/index.html`
- `legacy` serves templates and reads disk-backed config/data
- `POST /refresh` requires an authenticated user and uses session-held Yahoo
  tokens
- `normalize.py` ranking direction is `N = best`, `1 = worst`

### Without `REDIS_URL`

- Flask uses cookie sessions
- the app still starts
- but refreshed standings are not persisted for the React API flow

### With `REDIS_URL`

- Flask-Session stores sessions in Redis
- standings cache is stored in Redis by `user_id + league_id`
- standings cache TTL is 3600 seconds
- this is the intended runtime path for Docker, Docker Compose, and Fly.io

## Deployment Files

- `Dockerfile`
  - builds the React frontend in a Node stage
  - runs the app in `python:3.11-slim`
  - starts Gunicorn with 2 workers and a 120-second timeout
- `docker-compose.yml`
  - starts `app` + `redis`
  - wires `REDIS_URL=redis://redis:6379/0`
- `fly.toml`
  - app name: `roto-fantasy-solver`
  - region: `ord`
  - VM: `shared-cpu-1x`, `256mb`
  - health check: `GET /api/auth/status`

## Disk Files Still Used By Supported Code

- `data/config.json`: legacy-template config fallback
- `data/standings.json`: legacy-template standings fallback

`data/oauth2.json` still exists as a legacy fallback path inside
`src/fba/yahoo_api.py`, but the supported web flow does not require it.

## Verification Snapshot

Executed on March 3, 2026:

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`
- `npm --prefix frontend run build`
- Result: passed

Attempted on March 3, 2026:

- `./venv/bin/pytest -q`
- Result: collection failed because the checked-in `venv` is missing backend
  dependencies, including `python-dotenv`

Not executed as part of this verification pass:

- `docker compose up --build`
- `fly deploy`
