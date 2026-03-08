# Architecture Overview

Current as of March 7, 2026 (`main` local state).

## Runtime Modes

- `react` (default): session-driven, OAuth-backed, React UI served from
  `frontend/dist`
- `legacy`: disk-driven compatibility mode using Jinja templates

`FBA_UI_MODE=auto` is accepted but treated as `react` in `src/fba/app.py`.

## React Runtime Flow

```text
Browser
  -> GET /, /analysis, /games-played
     -> Flask serves frontend/dist/index.html
  -> React app
     -> GET /api/config
     -> GET /api/overview, /api/analysis, /api/games-played
     -> POST /api/config (set league_id in session)
     -> POST /refresh (auth required)
        -> refresh cooldown check (Redis key, 30s window)
        -> fba.auth.get_valid_tokens()
        -> fba.yahoo_api.get_oauth_session_from_tokens()
        -> fba.yahoo_api.fetch_standings()
        -> cache standings per user_id + league_id (Redis, 1h TTL)
```

`POST /refresh` returns `429` with `retry_after` when rate-limited.

## Session, Cache, and Persistence

### Without `REDIS_URL`

- Flask uses cookie-based sessions
- app still runs in both `react` and `legacy` modes
- refresh cooldown and league ID long-term persistence are effectively disabled
  (fail-open behavior)
- refreshed standings are not persisted for React API reads

### With `REDIS_URL`

- Flask-Session stores sessions in Redis (`fba:session:*`)
- standings cache keys: `fba:standings:{user_id}:{league_id}` (TTL 3600s)
- refresh cooldown keys: `fba:refresh_cooldown:{user_id}` (TTL 30s)
- long-term league ID keys: `fba:league_id:{user_id}` (TTL 1 year)
- OAuth callback/manual auth restore persisted `league_id` into session when
  available

## Docker Runtime

`Dockerfile` is a two-stage build:

1. `node:20-alpine` builds the React frontend
2. `python:3.11-slim` installs backend dependencies and runs Gunicorn

Container details:

- `PYTHONPATH=/app/src`
- `FBA_UI_MODE=react`
- non-root runtime user: `fba`
- exposed port: `8080`
- Gunicorn: `--workers 2 --timeout 120`

## Docker Compose Topology

`docker-compose.yml` defines:

- `redis` (`redis:7-alpine`, port `6379`, health-checked, persistent volume)
- `app` (built from `Dockerfile`, port `8080`, waits for healthy Redis)

Compose wiring:

- `REDIS_URL=redis://redis:6379/0`
- `YAHOO_REDIRECT_URI=http://localhost:8080/auth/yahoo/callback`
- `FBA_UI_MODE=react`

## Fly.io Topology

`fly.toml` defines:

- app: `roto-fantasy-solver`
- region: `ord`
- build source: `Dockerfile`
- internal port: `8080`
- VM: `shared-cpu-1x`, `256mb`
- HTTPS enforced
- machine auto-stop/auto-start enabled
- minimum running machines: `1`
- health check: `GET /api/auth/status`

Redis must be provided externally via `REDIS_URL`.

## Backend Modules

### `src/fba/app.py`

- Flask entrypoint, route registration, payload builders
- React vs legacy rendering selection
- conditional Redis-backed session setup
- per-user standings cache read/write
- per-user refresh cooldown checks (`429` + `retry_after`)
- league ID persistence/restore via Redis for authenticated users

### `src/fba/auth.py`

- Yahoo OAuth authorization URL generation
- auth code exchange and token refresh
- encrypted token storage in session (`Fernet`)
- Flask-Login integration

### `src/fba/yahoo_api.py`

- Yahoo Fantasy API standings fetch
- raw Yahoo team-stat fetch for `GP`
- app-schema roto category mapping
- legacy fallback support kept for archived tooling

### `src/fba/normalize.py`

- per-game normalization of Yahoo totals
- category re-ranking (`N = best`, `1 = worst`)
- `rank_total` and `points_delta` outputs

### `src/fba/analysis/category_targets.py`

- nearest-team effort/risk gaps (`gap_up`, `gap_down`, z versions)
- target score with 1st-place defensive branch
- independent `is_target` and `is_defend` flags
- `N_TARGETS = 3`, `N_DEFEND = 3`

### `src/fba/analysis/cluster_leverage.py`

- tier construction by distinct category values
- threshold window `T = 0.75`
- v1 count-based scores retained (`*_v1`)
- v2 distance-weighted scores active (`*_v2` -> `cluster_up_score` /
  `cluster_down_risk`)
- independent `is_target` / `is_defend` flags (`top 3` each)

### `src/fba/analysis/games_played.py`

- elapsed/remaining day math
- pace so far vs required pace
- net delta and `date_valid` handling

## Frontend Structure

- `frontend/src/main.tsx`: app entrypoint
- `frontend/src/App.tsx`: route map
- `frontend/src/components/`: shared UI primitives/shell
- `frontend/src/pages/`: route-level views
- `frontend/src/lib/`: API client, data types, formatters, async helpers

## Legacy Material

Deprecated tooling and exploratory scripts were moved to `legacy/` and are not
part of the supported runtime path.

## Verification Snapshot

Latest recorded verification (March 3, 2026):

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`
- `npm --prefix frontend run build`
- Result: passed

Not exercised in that pass:

- live `docker compose up --build`
- live `fly deploy`
