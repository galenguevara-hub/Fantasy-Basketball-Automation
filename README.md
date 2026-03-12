# Fantasy Basketball Automation

Yahoo Fantasy Basketball analysis app with a Flask backend, React frontend,
Yahoo OAuth login, and direct Yahoo Fantasy API refreshes.

## Current State (March 11, 2026)

Supported runtime/deployment path:

- `src/fba/app.py`
- `src/fba/auth.py`
- `src/fba/yahoo_api.py`
- `src/fba/normalize.py`
- `src/fba/analysis/`
- `frontend/`
- `Dockerfile`
- `docker-compose.yml`
- `fly.toml`

Archived one-off tooling and deprecated flows live in `legacy/`.

## Recent Functional Changes

- Dynamic league categories: Yahoo raw settings parsed at refresh time to build
  `CategoryConfig`; all ranking, normalization, gap, cluster, and projection
  logic is now driven by config — no more hard-coded 8-category assumptions
- Directionality support: categories with `higher_is_better=False` (e.g. TO in
  9-cat leagues) sort and gap-calculate correctly throughout the entire pipeline
- Frontend receives `category_config` in `/api/overview` and builds all column
  definitions dynamically; falls back to `DEFAULT_8CAT_CONFIG` for old files
- League validation on refresh: non-NBA leagues and non-roto scoring leagues are
  rejected immediately with a clear, specific error message
- Human-readable Yahoo API errors: raw bytes/JSON Yahoo error responses are
  parsed and shown as plain English messages
- Yahoo OAuth opens in a new browser tab (no longer navigates away from the app)
- Standings disk fallback: refreshed standings written to `data/standings.json`
  when Redis is unavailable; React mode works without Redis
- Rank Delta card removed from Executive Summary top metrics grid
- Redis-backed sessions when `REDIS_URL` is configured
- Redis-backed per-user standings cache (`user_id + league_id`) with 1-hour TTL
- Per-user refresh cooldown in Redis (`POST /refresh` returns `429` with
  `retry_after` when called again within 30 seconds)
- League ID persistence in Redis (`fba:league_id:{user_id}`) with 1-year TTL,
  restored on login/callback
- Layer 1 analysis exposes independent `is_target` and `is_defend` flags
  (categories can be both)
- Cluster analysis uses v2 distance-weighted scoring as active output, with v1
  scores retained for diagnostics/rollback
- Executive Summary is the default React landing page (`/`)
- Standings view at dedicated client route (`/standings`)

## Environment Variables

Core configuration:

- `SECRET_KEY`
- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `YAHOO_REDIRECT_URI`
- `TOKEN_ENCRYPTION_KEY` (recommended in production)

Deployment/runtime:

- `REDIS_URL`
  Required for production-style multi-instance deployments and for the current
  persisted React refresh flow.

See `.env.example` for the current template.

## Local Setup (Non-Docker)

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend install
cp .env.example .env
npm --prefix frontend run build
```

Important:

- Without `REDIS_URL`, the app starts and standings are persisted to
  `data/standings.json` as a disk fallback — React mode works without Redis
- For the full multi-user experience with refresh cooldowns and league ID
  persistence, run Redis and set `REDIS_URL`

## Run Locally (Non-Docker)

```bash
./scripts/start_server.sh
```

For split frontend/backend development:

```bash
./scripts/start_dev.sh
```

- Flask API: `http://localhost:8080`
- Vite UI: `http://localhost:5173`

`vite.config.ts` proxies `/api`, `/refresh`, `/auth`, and `/logout` to Flask.

## Run With Docker Compose

`docker-compose.yml` defines:

- `app`: Flask + React container built from `Dockerfile`
- `redis`: Redis 7 for sessions, standings cache, refresh cooldown keys, and
  persisted league IDs

```bash
docker compose up --build
```

App URL: `http://localhost:8080`

Compose defaults:

- `YAHOO_REDIRECT_URI=http://localhost:8080/auth/yahoo/callback`
- `REDIS_URL=redis://redis:6379/0`
- `FBA_UI_MODE=react`

Provide `YAHOO_CLIENT_ID` and `YAHOO_CLIENT_SECRET` in your shell or `.env`.

## Docker Image Notes

`Dockerfile` is a two-stage build:

1. `node:20-alpine` builds React
2. `python:3.11-slim` runs Flask with Gunicorn

Runtime details:

- non-root `fba` user
- port `8080`
- Gunicorn `--workers 2 --timeout 120`

## Fly.io Deployment

`fly.toml` currently configures:

- app: `roto-fantasy-solver`
- region: `ord`
- internal port: `8080`
- VM: `shared-cpu-1x`, `256mb`
- machine auto-stop/auto-start enabled
- minimum running machines: `1`
- health check: `GET /api/auth/status`

Set production secrets before deploy:

- `SECRET_KEY`
- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `YAHOO_REDIRECT_URI`
- `TOKEN_ENCRYPTION_KEY`
- `REDIS_URL`

## Runtime Behavior Summary

React mode is session-driven:

- `session["league_id"]` stores the active league
- `session["yahoo_tokens"]` stores encrypted Yahoo tokens
- React route map defaults to Executive Summary on `/`
- Standings table page is available from the app menu via `/standings`

With `REDIS_URL`:

- Flask-Session stores session data in Redis
- standings cache is persisted in Redis per `user_id + league_id`
- refresh cooldown and long-term league ID persistence are active

Without `REDIS_URL`:

- app uses cookie-based sessions
- refresh cooldown and league ID persistence are effectively disabled (fail-open)
- refreshed standings are written to `data/standings.json` and read back on all
  API calls (disk fallback)

Legacy template mode still reads:

- `data/config.json`
- `data/standings.json`

## Verification Snapshot

Latest recorded verification (March 11, 2026):

- `./venv/bin/pytest -q` → `192 passed`
- `npm --prefix frontend run build` → passed
- Deployed to `https://roto-fantasy-solver.fly.dev`

## Docs

- `docs/QUICKSTART.md`
- `docs/ARCHITECTURE.md`
- `docs/DOCS.md`
- `docs/CHANGELOG.md`
- `docs/IMPLEMENTATION_SUMMARY.md`
- `frontend/README.md`
- `legacy/README.md`
