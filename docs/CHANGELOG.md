# Changelog

## 2026-03-03

### Documentation refresh for deployment changes

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

### Verification snapshot

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
