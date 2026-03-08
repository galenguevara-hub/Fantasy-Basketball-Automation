# Implementation Summary

Status: current as of March 7, 2026.

## What Is Implemented

- Flask web app in `src/fba/app.py`
- React UI in `frontend/`
- Legacy Jinja UI in `src/fba/templates/`
- Yahoo OAuth login and encrypted session token storage in `src/fba/auth.py`
- Direct Yahoo Fantasy API refresh path in `src/fba/yahoo_api.py`
- Per-game normalization in `src/fba/normalize.py`
- Layer 1 category target/defend analysis in `src/fba/analysis/category_targets.py`
- Layer 2 cluster leverage analysis in `src/fba/analysis/cluster_leverage.py`
- Games-played pace analysis in `src/fba/analysis/games_played.py`
- Multi-stage Docker build in `Dockerfile`
- Local Docker + Redis stack in `docker-compose.yml`
- Fly.io deployment config in `fly.toml`
- Redis-backed sessions/cache/cooldown/persistence features when `REDIS_URL` is set

## Active Endpoints (`src/fba/app.py`)

- `GET /`
- `GET /analysis`
- `GET /games-played`
- `GET /auth/yahoo`
- `GET /debug/auth-url`
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
- `GET /assets/<path:filename>`

## Runtime Notes

- Default mode is `FBA_UI_MODE=react`
- `react` and `auto` require `frontend/dist/index.html`
- `legacy` serves templates and reads disk-backed config/data
- `POST /refresh` requires authentication and valid Yahoo tokens
- `POST /refresh` has a per-user 30-second cooldown when Redis is available
  and returns `429` with `retry_after`
- `normalize.py` ranking direction is `N = best`, `1 = worst`

### Without `REDIS_URL`

- Flask uses cookie sessions
- app still starts
- refresh cooldown and league ID long-term persistence are disabled
- refreshed standings are not persisted for React API reads

### With `REDIS_URL`

- Flask-Session stores sessions in Redis
- standings cache keys: `fba:standings:{user_id}:{league_id}`
- standings cache TTL: `3600` seconds
- refresh cooldown keys: `fba:refresh_cooldown:{user_id}` (TTL `30` seconds)
- league ID persistence keys: `fba:league_id:{user_id}` (TTL `1 year`)
- this is the intended runtime path for Docker Compose and Fly.io

## Analysis Behavior Notes

- Layer 1 (`category_targets.py`):
  - score includes first-place defensive branch (`DEFEND_WEIGHT / max(z_gap_down, EPS)`)
  - `TARGET` and `DEFEND` are independent (`is_target`, `is_defend`)
  - `N_TARGETS = 3`, `N_DEFEND = 3`
- Layer 2 (`cluster_leverage.py`):
  - v1 count-based scores are retained (`cluster_*_v1`)
  - v2 distance-weighted scores are active (`cluster_*_v2` -> `cluster_up_score` / `cluster_down_risk`)
  - `TARGET` and `DEFEND` are independent (`top 3` each)

## Deployment Files

- `Dockerfile`
  - builds React in `node:20-alpine`
  - runs app in `python:3.11-slim` with Gunicorn (`2` workers, `120s` timeout)
- `docker-compose.yml`
  - starts `app` + `redis`
  - wires `REDIS_URL=redis://redis:6379/0`
- `fly.toml`
  - app: `roto-fantasy-solver`
  - region: `ord`
  - VM: `shared-cpu-1x`, `256mb`
  - minimum machines running: `1`
  - health check: `GET /api/auth/status`

## Disk Files Still Used By Supported Code

- `data/config.json`: legacy-template config fallback
- `data/standings.json`: legacy-template standings fallback

`data/oauth2.json` remains only as a legacy fallback inside
`src/fba/yahoo_api.py`; the supported web OAuth flow does not require it.

## Verification Snapshot

Latest recorded verification (March 3, 2026):

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`
- `npm --prefix frontend run build`
- Result: passed

Also recorded on March 3, 2026:

- `./venv/bin/pytest -q` failed during collection in checked-in `venv` because
  backend dependencies (including `python-dotenv`) were missing there
