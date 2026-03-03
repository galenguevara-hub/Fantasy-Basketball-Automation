# Fantasy Basketball Automation

Yahoo Fantasy Basketball analysis app with a Flask backend, a React frontend,
Yahoo OAuth login, and direct Yahoo Fantasy API refreshes.

## Current State

As of March 3, 2026, the latest local deployment work is present on:

- `main`
- `feat/saas-dev`

Older branches such as `saas` and `deploy/railway` stop before the Docker and
Fly.io deployment changes.

The supported runtime path is:

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

## What Changed Recently

The latest deployment changes added:

- multi-stage Docker build for the React frontend + Python backend
- Gunicorn as the production process inside the container
- Redis-backed server sessions when `REDIS_URL` is configured
- Redis-backed per-user standings cache with a 1-hour TTL
- `docker-compose.yml` for local container development with Redis
- `fly.toml` for Fly.io deployment

## Environment Variables

Core app configuration:

- `SECRET_KEY`
- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `YAHOO_REDIRECT_URI`
- `TOKEN_ENCRYPTION_KEY` (recommended in production)

Deployment-specific:

- `REDIS_URL`
  Required for production-style multi-instance deployments so sessions and the
  standings cache live outside a single process.

See `.env.example` for the current local template.

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

- for the current multi-user React refresh flow, you also need a reachable
  Redis instance behind `REDIS_URL`, or you should use Docker Compose instead
- without `REDIS_URL`, the app starts, but refreshed React-mode standings are
  not persisted by the current code path

## Run Locally (Non-Docker)

```bash
./scripts/start_server.sh
```

For a fully working local React refresh flow, pair this with a running Redis
instance and `REDIS_URL`.

For split frontend/backend development:

```bash
./scripts/start_dev.sh
```

- Flask API: `http://localhost:8080`
- Vite UI: `http://localhost:5173`

`vite.config.ts` proxies `/api`, `/refresh`, `/auth`, and `/logout` to the
Flask backend during frontend development.

## Run With Docker Compose

The repo now includes `docker-compose.yml` for a production-like local stack:

- `app`: the Flask + React container built from `Dockerfile`
- `redis`: Redis 7 used for sessions and cached standings

Start it with:

```bash
docker compose up --build
```

The app will be available at `http://localhost:8080`.

Important compose defaults:

- `YAHOO_REDIRECT_URI` is set to `http://localhost:8080/auth/yahoo/callback`
- `REDIS_URL` is set to `redis://redis:6379/0`
- `FBA_UI_MODE` is forced to `react`

You must still provide `YAHOO_CLIENT_ID` and `YAHOO_CLIENT_SECRET` in your
shell environment or `.env` file before starting compose.

## Docker Image Notes

`Dockerfile` now builds in two stages:

1. `node:20-alpine` builds the React frontend
2. `python:3.11-slim` runs the Flask app with Gunicorn

Runtime behavior:

- runs as a non-root `fba` user
- exposes port `8080`
- starts Gunicorn with 2 workers
- uses a 120-second timeout to tolerate slow Yahoo API calls

`.dockerignore` excludes `data/`, local secrets, tests, docs, scripts, and git
metadata from the runtime image.

## Fly.io Deployment

The repo now includes `fly.toml` for Fly.io.

Current Fly config:

- app name: `roto-fantasy-solver`
- primary region: `ord`
- internal port: `8080`
- VM size: `shared-cpu-1x`
- memory: `256mb`
- auto stop/start enabled
- health check path: `/api/auth/status`

Before deploying, provision a Redis instance and set the required secrets:

- `SECRET_KEY`
- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `YAHOO_REDIRECT_URI`
- `TOKEN_ENCRYPTION_KEY`
- `REDIS_URL`

Then deploy with the Fly CLI using the checked-in `fly.toml`.

## App Behavior

React mode is session-driven:

- `session["league_id"]` stores the active league ID
- `session["yahoo_tokens"]` stores encrypted Yahoo tokens

When `REDIS_URL` is configured:

- Flask-Session stores sessions in Redis
- standings are cached in Redis per user + league
- this is the intended runtime path for Docker and Fly.io

When `REDIS_URL` is not configured:

- the app falls back to cookie-based sessions
- but the current React refresh flow does not persist fresh standings because
  cache writes are Redis-only

Legacy template mode still reads:

- `data/config.json`
- `data/standings.json`

## Verification Snapshot

Verified on March 3, 2026:

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`
- `npm --prefix frontend run build`
- Result: passed

Still true on March 3, 2026:

- `./venv/bin/pytest -q` fails during collection in the checked-in `venv`
  because backend packages such as `python-dotenv` are not installed there

I did not run a full container build or a live Fly deploy as part of this docs
refresh.

## Docs

- `docs/QUICKSTART.md`
- `docs/ARCHITECTURE.md`
- `docs/DOCS.md`
- `docs/CHANGELOG.md`
- `docs/IMPLEMENTATION_SUMMARY.md`
- `frontend/README.md`
- `legacy/README.md`
