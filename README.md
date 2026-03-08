# Fantasy Basketball Automation

Yahoo Fantasy Basketball analysis app with a Flask backend, React frontend,
Yahoo OAuth login, and direct Yahoo Fantasy API refreshes.

## Current State (March 7, 2026)

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

- Redis-backed sessions when `REDIS_URL` is configured
- Redis-backed per-user standings cache (`user_id + league_id`) with 1-hour TTL
- Per-user refresh cooldown in Redis (`POST /refresh` returns `429` with
  `retry_after` when called again within 30 seconds)
- League ID persistence in Redis (`fba:league_id:{user_id}`) with 1-year TTL,
  restored on login/callback
- Layer 1 analysis now exposes independent `is_target` and `is_defend` flags
  (categories can be both)
- Cluster analysis now uses v2 distance-weighted scoring as active output, with
  v1 scores retained for diagnostics/rollback
- Analysis UI summary cards split into `L1` and `Cluster` sections and sorted
  by priority score

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

- For the current multi-user React flow, run Redis and set `REDIS_URL`
- Without `REDIS_URL`, the app starts, but refreshed React-mode standings are
  not persisted by the current code path

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

With `REDIS_URL`:

- Flask-Session stores session data in Redis
- standings cache is persisted in Redis per `user_id + league_id`
- refresh cooldown and long-term league ID persistence are active

Without `REDIS_URL`:

- app uses cookie-based sessions
- refresh cooldown and league ID persistence are effectively disabled (fail-open)
- React refresh responses are not persisted across requests

Legacy template mode still reads:

- `data/config.json`
- `data/standings.json`

## Verification Snapshot

Latest recorded verification (March 3, 2026):

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`
- `npm --prefix frontend run build`
- Result: passed

Known local caveat:

- `./venv/bin/pytest -q` can fail during collection in the checked-in `venv`
  if backend packages (for example `python-dotenv`) are missing there

## Docs

- `docs/QUICKSTART.md`
- `docs/ARCHITECTURE.md`
- `docs/DOCS.md`
- `docs/CHANGELOG.md`
- `docs/IMPLEMENTATION_SUMMARY.md`
- `frontend/README.md`
- `legacy/README.md`
