# React Frontend

This directory contains the React + Vite UI for the main `FBA_UI_MODE=react` experience.

## Routes

- `/`: standings overview
- `/analysis`: category target and cluster leverage analysis
- `/games-played`: games-played pace analysis

## Backend Contracts

The frontend depends on these backend endpoints:

- `GET /api/auth/status`
- `POST /logout`
- `GET /api/config`
- `POST /api/config`
- `GET /api/overview`
- `GET /api/analysis`
- `GET /api/games-played`
- `POST /refresh`

Auth initiation is handled by browser navigation to `GET /auth/yahoo` when the UI receives a `401`.

## Page Behavior

- `OverviewPage` renders four sortable tables: overall standings, raw stats, per-game averages, and per-game category rankings.
- `OverviewPage` attempts one automatic refresh when a league ID exists but no cached data is loaded yet.
- `AnalysisPage` stores the selected team in `?team=<TEAM_NAME>`.
- `AnalysisPage` renders both layer-1 target scoring and layer-2 cluster leverage.
- `GamesPlayedPage` stores filters in `?start=YYYY-MM-DD&end=YYYY-MM-DD&total_games=<N>`.
- `DataTable` provides client-side sorting for every column header.

## Local Development

From the repo root:

```bash
./scripts/start_dev.sh
```

Or run only the frontend:

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation/frontend"
npm install
npm run dev
```

Vite runs on `http://localhost:5173`.

Proxy rules in `vite.config.ts` forward:

- `/api` -> `http://localhost:8080`
- `/refresh` -> `http://localhost:8080`

In the current setup, `/auth/*` and `/logout` are not proxied by Vite. That means OAuth login/logout works out of the box on the Flask-served app at `http://localhost:8080`; if you use the Vite origin at `http://localhost:5173`, add matching proxy rules first.

## Production Build

Build the bundle Flask serves in default mode:

```bash
npm run build
```

`src/fba/app.py` serves `frontend/dist/index.html` for `/`, `/analysis`, and `/games-played` when `FBA_UI_MODE` is `react` (or `auto`).
