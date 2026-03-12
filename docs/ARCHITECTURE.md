# Architecture Overview

Current as of March 11, 2026 (`main`).

## Runtime Modes

- `react` (default): session-driven, OAuth-backed, React UI served from
  `frontend/dist`
- `legacy`: disk-driven compatibility mode using Jinja templates

`FBA_UI_MODE=auto` is accepted but treated as `react` in `src/fba/app.py`.

## React Runtime Flow

```text
Browser
  -> GET /, /executive-summary, /analysis, /games-played
     -> Flask serves frontend/dist/index.html
  -> React app
     -> GET /api/config
     -> GET /api/overview, /api/executive-summary, /api/analysis, /api/games-played
     -> POST /api/config (set league_id in session)
     -> POST /refresh (auth required)
        -> refresh cooldown check (Redis key, 30s window)
        -> fba.auth.get_valid_tokens()
        -> fba.yahoo_api.get_oauth_session_from_tokens()
        -> fba.yahoo_api.fetch_standings()
           -> validates sport (NBA only) and scoring type (roto only)
           -> builds CategoryConfig from Yahoo raw settings
        -> cache standings per user_id + league_id (Redis, 1h TTL)
        -> disk fallback: writes data/standings.json when Redis unavailable
```

React route behavior:

- `/` defaults to Executive Summary
- `/standings` is used for in-app navigation to the standings page
- `/executive-summary` is an explicit alias route

`POST /refresh` returns `429` with `retry_after` when rate-limited.

## Session, Cache, and Persistence

### Without `REDIS_URL`

- Flask uses cookie-based sessions
- app still runs in both `react` and `legacy` modes
- refresh cooldown and league ID long-term persistence are effectively disabled
  (fail-open behavior)
- refreshed standings are written to `data/standings.json` and read back on
  all subsequent API calls (disk fallback introduced March 11, 2026)

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
- executive-summary payload builder and API route wiring

### `src/fba/auth.py`

- Yahoo OAuth authorization URL generation
- auth code exchange and token refresh
- encrypted token storage in session (`Fernet`)
- Flask-Login integration

### `src/fba/category_config.py`

- `CategoryConfig` dataclass: single source of truth for per-category metadata
- `KNOWN_STATS` dict mapping Yahoo `stat_id` → key, display, directionality
- `build_category_config_from_raw()`: parses Yahoo raw settings JSON to produce
  a `CategoryConfig` list dynamically at refresh time
- `DEFAULT_8CAT_CONFIG`: fallback config for old standings files without
  embedded config
- `to_serializable()` / `from_serializable()`: JSON round-trip for storage

### `src/fba/yahoo_api.py`

- Yahoo Fantasy API standings fetch with league validation (NBA + roto only)
- builds `CategoryConfig` from Yahoo raw settings at each refresh
- raw Yahoo team-stat fetch for `GP` using dynamic stat_id map
- human-readable error translation for Yahoo API error responses
- legacy fallback support kept for archived tooling

### `src/fba/normalize.py`

- per-game normalization driven by `CategoryConfig` (counting vs percentage)
- category re-ranking (`N = best`, `1 = worst`) respecting `higher_is_better`
- `rank_total` and `points_delta` outputs

### `src/fba/analysis/category_targets.py`

- nearest-team effort/risk gaps (`gap_up`, `gap_down`, z versions) respecting
  `higher_is_better` directionality
- target score with 1st-place defensive branch
- independent `is_target` and `is_defend` flags
- `N_TARGETS = 3`, `N_DEFEND = 3`

### `src/fba/analysis/cluster_leverage.py`

- tier construction by distinct category values respecting directionality
- threshold window `T = 0.75`
- v1 count-based scores retained (`*_v1`)
- v2 distance-weighted scores active (`*_v2` -> `cluster_up_score` /
  `cluster_down_risk`)
- `tag` field: `TARGET` and `DEFEND` are mutually exclusive; `is_defend` flag
  marks all top-N defend candidates regardless of TARGET status

### `src/fba/analysis/games_played.py`

- elapsed/remaining day math
- pace so far vs required pace
- net delta and `date_valid` handling

### `src/fba/analysis/executive_summary.py`

- composes normalization + layer-1 + cluster + pace + projection outputs
- builds a decision dashboard payload for one selected team
- powers both top-level executive summary copy and tabular sections

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

Latest recorded verification (March 11, 2026):

- `./venv/bin/pytest -q` → `192 passed`
- `npm --prefix frontend run build` → passed
- `flyctl deploy --remote-only` → deployed to `https://roto-fantasy-solver.fly.dev`
