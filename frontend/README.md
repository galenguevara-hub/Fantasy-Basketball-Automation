# React Frontend

This directory contains the supported React + Vite UI for the default
`FBA_UI_MODE=react` experience.

## Routes

- `/`: executive summary decision dashboard (default landing page)
- `/executive-summary`: executive summary alias route
- `/standings`: standings, raw totals, per-game tables, and per-game rank totals
- `/analysis`: Layer 1 category analysis plus Layer 2 cluster leverage
- `/games-played`: games-played pace and season-window controls

## Backend Contracts

The frontend uses:

- `GET /api/auth/status`
- `POST /logout`
- `GET /api/config`
- `POST /api/config`
- `GET /api/overview`
- `GET /api/executive-summary`
- `GET /api/analysis`
- `GET /api/games-played`
- `POST /refresh`

Refresh/auth behavior:

- `401` triggers OAuth in a new tab (`window.open("/auth/yahoo", "_blank")`)
- `429` from `/refresh` is parsed via `retry_after` and shown as a countdown
  in `LeagueControls`

## Analysis UI Semantics

Layer 1 table and summary:

- uses backend flags `is_target` and `is_defend` (independent)
- categories can display as both TARGET and DEFEND
- summary cards are split by `L1` and `Cluster` sections and sorted by
  priority score

Cluster table:

- displays active cluster scores from backend (`cluster_up_score`,
  `cluster_down_risk`)
- explanatory copy reflects the active distance-weighted cluster scoring model
- `tag` field: `TARGET` and `DEFEND` are mutually exclusive; `is_defend` flag
  marks all top-N defend candidates regardless of TARGET status

## Dynamic Category Support

- `GET /api/overview` response includes `category_config` array when the
  league has been refreshed with the current backend
- `OverviewPage` builds all category column definitions dynamically from config
- falls back to `DEFAULT_8CAT_CONFIG` (8-cat hardcoded) for old standings files
  without embedded config

## Table Behaviors

- `DataTable` supports `initialSort`, optional `tieBreaker`, and custom
  `sortValue` per column
- overview FG%/FT% columns sort using hidden roto sort keys for stable rank
  order
- team columns are first in main tables for consistent scanning

## Code Layout

- `src/main.tsx`: entrypoint
- `src/App.tsx`: route map
- `src/components/`: shared UI
- `src/pages/`: route components
- `src/lib/`: API client, types, formatting, async helpers

The frontend codebase is TypeScript-only.

## Local Development

From repo root:

```bash
./scripts/start_dev.sh
```

Frontend only:

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation/frontend"
npm install
npm run dev
```

Vite runs on `http://localhost:5173`.

`vite.config.ts` proxies:

- `/api` -> `http://localhost:8080`
- `/refresh` -> `http://localhost:8080`
- `/auth` -> `http://localhost:8080`
- `/logout` -> `http://localhost:8080`

## Production Build

```bash
npm run build
```

`src/fba/app.py` serves `frontend/dist/index.html` for `/`,
`/executive-summary`, `/analysis`, and `/games-played` when `FBA_UI_MODE` is
`react` (and when `auto` is supplied, since `auto` is treated as `react`).

`/standings` is a client route in `src/App.tsx` used during in-app navigation.

## Docker/Fly Integration

- frontend builds in Docker stage 1 (`node:20-alpine`)
- built assets are copied into the Python runtime image
- Flask serves `frontend/dist` directly

Result:

- Docker and Fly.io run the same bundled frontend artifact
- production has no separate frontend container
- `docker-compose.yml` runs only `app` + `redis`
