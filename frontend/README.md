# React Frontend

This directory contains the supported React + Vite UI for the app's default
`FBA_UI_MODE=react` experience.

## Routes

- `/`: standings overview
- `/analysis`: category target and cluster leverage analysis
- `/games-played`: games-played pace analysis

## Backend Contracts

The frontend depends on:

- `GET /api/auth/status`
- `POST /logout`
- `GET /api/config`
- `POST /api/config`
- `GET /api/overview`
- `GET /api/analysis`
- `GET /api/games-played`
- `POST /refresh`

Auth initiation is handled by browser navigation to `GET /auth/yahoo` when the
UI receives a `401`.

## Code Layout

- `src/main.tsx`: entrypoint
- `src/App.tsx`: route map
- `src/components/`: shared UI
- `src/pages/`: route components
- `src/lib/`: API, formatting, and async helpers

The frontend is TypeScript-only.

## Local Development

From the repo root:

```bash
./scripts/start_dev.sh
```

Or frontend only:

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

`src/fba/app.py` serves `frontend/dist/index.html` for `/`, `/analysis`, and
`/games-played` when `FBA_UI_MODE` is `react` or `auto`.

## Docker Integration

The frontend is built inside the first stage of `Dockerfile` using
`node:20-alpine`.

The built assets are then copied into the Python runtime image and served by
Flask from `frontend/dist`.

That means:

- Docker and Fly.io use the same built frontend artifact
- there is no separate frontend container in production
- `docker-compose.yml` only runs two services: `app` and `redis`
