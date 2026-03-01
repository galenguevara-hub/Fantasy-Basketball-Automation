# Implementation Summary

Status: current as of March 1, 2026.

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
- React-mode refreshed standings are stored in `_standings_cache`, keyed by
  `league_id`
- `normalize.py` ranking direction is `N = best`, `1 = worst`

## Disk Files Still Used By Supported Code

- `data/config.json`: legacy-template config fallback
- `data/standings.json`: legacy-template standings fallback

`data/oauth2.json` still exists as a legacy fallback path inside
`src/fba/yahoo_api.py`, but the supported web flow does not require it.

## Cleanup Notes

- Deprecated utilities and exploratory scripts were moved to `legacy/`
- The frontend duplicate `.js` files were removed
- `frontend/tsconfig.tsbuildinfo` is no longer tracked
- old documentation handoff text files were removed

## Verification Snapshot

Executed on March 1, 2026:

- `./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py`
- Result: `120 passed`

Attempted on March 1, 2026:

- `./venv/bin/pytest -q`
- Result: collection failed because the checked-in `venv` is missing backend
  dependencies, including `python-dotenv` and `flask-login`
