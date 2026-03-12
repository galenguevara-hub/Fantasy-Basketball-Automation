# Changelog

## 2026-03-11

### Dynamic league categories + error handling + UX improvements

- Added `src/fba/category_config.py` as a single source of truth for category
  metadata (`CategoryConfig` dataclass with `key`, `display`, `stat_id`,
  `higher_is_better`, `is_percentage`, `per_game_key`, `rank_key`)
- Yahoo raw settings are parsed at refresh time to build a `CategoryConfig`
  list dynamically; stored in standings payload as `league.category_config`
- All ranking, per-game normalization, gap calculation, cluster scoring, game
  projection, and executive summary logic is now driven by config — no more
  hard-coded 8-category assumptions
- Directionality support: categories with `higher_is_better=False` (e.g. TO in
  9-cat leagues) sort and gap-calculate correctly throughout the entire pipeline
- Frontend receives `category_config` in `/api/overview` response and builds
  all column definitions dynamically; falls back to `DEFAULT_8CAT_CONFIG` for
  old standings files without embedded config
- DEFEND cluster tag is mutually exclusive with TARGET at the `tag` field
  level; `is_defend` flag still marks all top-N defend candidates
- `defends` list in `league_summary` sorted by `z_gap_down` ascending
  (tightest gap = highest priority defend)
- Yahoo OAuth redirect now opens in a new browser tab
- Standings disk fallback: when `REDIS_URL` is not configured, refreshed
  standings are now written to `data/standings.json` and read back on all API
  calls — React mode works without Redis
- Human-readable Yahoo API errors: raw bytes/JSON Yahoo error responses are
  parsed and shown as plain English messages
- League validation on refresh: non-NBA leagues and non-roto scoring leagues
  are rejected immediately with a clear, specific error message
- Removed Rank Delta metric card from Executive Summary top metrics grid
- 192/192 tests passing

### Verification snapshot

- `./venv/bin/pytest -q` → `192 passed`
- `npm --prefix frontend run build` → passed
- Deployed to `https://roto-fantasy-solver.fly.dev`

## 2026-03-08

### Executive summary and docs alignment

- Made Executive Summary the default React landing page (`/`).
- Added/maintained explicit executive routes:
  - `GET /executive-summary`
  - `GET /api/executive-summary`
- Added/maintained in-app standings route (`/standings`) for the previous
  standings dashboard view.
- Updated executive summary presentation details:
  - card/metric visual emphasis
  - equal-games-played rank copy updates
  - projected standings difference column
  - category/team chip-heavy summary styling

### Documentation sync to latest app behavior

- Updated all primary docs to match current runtime and route behavior:
  - `README.md`
  - `frontend/README.md`
  - `docs/QUICKSTART.md`
  - `docs/ARCHITECTURE.md`
  - `docs/IMPLEMENTATION_SUMMARY.md`
  - `docs/DOCS.md`
- Added documentation for `src/fba/analysis/executive_summary.py`.
- Updated verification snapshots to March 8, 2026:
  - `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_games_played.py tests/test_executive_summary.py` (`78 passed`)
  - `npm --prefix frontend run build` (passed)

## 2026-03-07

### Documentation sync to latest code behavior

- Updated all primary knowledge docs (`README`, `QUICKSTART`, `ARCHITECTURE`,
  `IMPLEMENTATION_SUMMARY`, `DOCS`, `frontend/README`) to match current
  `main` runtime behavior.
- Removed stale endpoint references (`GET /api/standings`) from docs.
- Added current backend behavior details:
  - per-user refresh cooldown in Redis (`30s`, `429` + `retry_after`)
  - Redis standings cache key/TTL (`fba:standings:{user_id}:{league_id}`,
    `3600s`)
  - Redis league ID persistence key/TTL (`fba:league_id:{user_id}`, `1 year`)
  - restore-on-login league ID behavior
- Added current analysis behavior details:
  - Layer 1 `TARGET`/`DEFEND` independence with `is_target` / `is_defend`
  - Cluster v2 distance-weighted scoring as active output, with v1 retained
  - top-3 target/defend semantics for both layers
- Updated deployment docs to match checked-in config:
  - Fly `min_machines_running = 1`
  - Docker Compose Redis responsibilities (sessions/cache/cooldown/persistence)

## 2026-03-03

### Documentation refresh and deployment changes

- Scanned the latest local branch tips and updated the docs for the current
  `main` / `feat/saas-dev` state.
- Added explicit documentation for:
  - `Dockerfile`
  - `docker-compose.yml`
  - `fly.toml`
  - Redis-backed sessions and per-user standings cache
- Updated the docs to distinguish:
  - local shell development
  - Docker Compose local runtime
  - Fly.io deployment
- Updated verification notes to the current March 3, 2026 status.

### Verification (March 3, 2026)

- Executed on March 3, 2026:
  - `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
  - Result: `120 passed`
  - `npm --prefix frontend run build`
  - Result: passed
- Attempted on March 3, 2026:
  - `./venv/bin/pytest -q`
  - Current checked-in `venv` still fails during collection because backend
    dependencies such as `python-dotenv` are missing there

## 2026-03-02

### Deployment changes landed in code

- Added Fly.io deployment support with Docker and Redis.
- Added `Dockerfile`, `docker-compose.yml`, and `fly.toml`.
- Added Gunicorn for the production container entrypoint.
- Added Redis-backed sessions and cache support through `REDIS_URL`.
- Finalized the Fly.io app name as `roto-fantasy-solver`.

## 2026-03-01

### Repository cleanup

- Moved deprecated tooling into `legacy/`.
- Removed the duplicate frontend `.js` source files and kept the React app
  TypeScript-only.
- Removed `frontend/tsconfig.tsbuildinfo` from version control and ignored it.
- Removed the tracked `data/browser_state.json` runtime artifact.
- Removed the one-off documentation handoff files in `docs/`.

### Documentation synchronization

- Rewrote the docs around the supported Yahoo OAuth web flow in `src/fba/auth.py`
  and the direct refresh path in `src/fba/yahoo_api.py`.
- Simplified the docs to distinguish the supported path from the archived
  `legacy/` material.
