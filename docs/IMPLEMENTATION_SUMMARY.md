# Implementation Summary

Status: current as of March 11, 2026.

## What Is Implemented

- Flask web app in `src/fba/app.py`
- React UI in `frontend/`
- Legacy Jinja UI in `src/fba/templates/`
- Yahoo OAuth login and encrypted session token storage in `src/fba/auth.py`
- Direct Yahoo Fantasy API refresh path in `src/fba/yahoo_api.py`
- League category metadata as single source of truth in `src/fba/category_config.py`
- Per-game normalization in `src/fba/normalize.py`
- Layer 1 category target/defend analysis in `src/fba/analysis/category_targets.py`
- Layer 2 cluster leverage analysis in `src/fba/analysis/cluster_leverage.py`
- Games-played pace analysis in `src/fba/analysis/games_played.py`
- Executive summary synthesis layer in `src/fba/analysis/executive_summary.py`
- Multi-stage Docker build in `Dockerfile`
- Local Docker + Redis stack in `docker-compose.yml`
- Fly.io deployment config in `fly.toml`
- Redis-backed sessions/cache/cooldown/persistence features when `REDIS_URL` is set
- Disk-based standings fallback when Redis is unavailable (`data/standings.json`)

## Active Endpoints (`src/fba/app.py`)

- `GET /`
- `GET /analysis`
- `GET /games-played`
- `GET /executive-summary`
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
- `GET /api/executive-summary`
- `POST /refresh`
- `GET /assets/<path:filename>`

## Runtime Notes

- Default mode is `FBA_UI_MODE=react`
- React homepage is Executive Summary (`/`)
- Standings are available via React route `/standings` in the app menu
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
- refreshed standings are written to `data/standings.json` and read back on all
  subsequent API calls (disk fallback introduced March 11, 2026)

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
  - `TARGET` and `DEFEND` are independent (`is_target`, `is_defend`); categories
    can be both simultaneously
  - directionality respects `higher_is_better` from `CategoryConfig` (e.g. TO)
  - `N_TARGETS = 3`, `N_DEFEND = 3`
- Layer 2 (`cluster_leverage.py`):
  - v1 count-based scores are retained (`cluster_*_v1`)
  - v2 distance-weighted scores are active (`cluster_*_v2` -> `cluster_up_score` / `cluster_down_risk`)
  - `tag` field: `TARGET` and `DEFEND` are mutually exclusive; `is_defend` flag
    marks all top-N defend candidates regardless of TARGET status
  - `defends` list in `league_summary` sorted by `z_gap_down` ascending
    (tightest gap = highest priority defend)

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
- `data/standings.json`: standings disk fallback (written after every refresh
  when Redis is unavailable; read back on all API calls as last-resort fallback)

`data/oauth2.json` remains only as a legacy fallback inside
`src/fba/yahoo_api.py`; the supported web OAuth flow does not require it.

## Verification Snapshot

Latest recorded verification (March 11, 2026):

- `./venv/bin/pytest -q` → `192 passed`
- `npm --prefix frontend run build` → passed
- Deployed to `https://roto-fantasy-solver.fly.dev`
