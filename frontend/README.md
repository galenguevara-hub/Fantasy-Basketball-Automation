# React Frontend

This directory contains the Vite + React + TypeScript frontend for the Fantasy Basketball app.

## Routes

- `/` Standings overview
- `/analysis` Category targets analysis
- `/games-played` Games played pace analysis

## UI Behavior Defaults

- `/` Per-Game Category Rankings defaults to `Total` descending.
- `/analysis` Category Analysis defaults to `Score` descending.
- `/analysis` Cluster Leverage defaults to `Up Score` descending.
- `/analysis` stores selected team in `?team=...`.
- `/games-played` stores filters in `?start=...&end=...&total_games=...`.

## API Dependencies

The frontend reads data from the Flask backend:

- `GET /api/overview`
- `GET /api/analysis`
- `GET /api/games-played`
- `GET /api/config`
- `POST /api/config`
- `POST /refresh`

## Local Development

1. Start Flask backend on `http://localhost:8080`.
2. Install frontend dependencies:

```bash
npm install
```

3. Run Vite dev server:

```bash
npm run dev
```

Vite proxies `/api` and `/refresh` calls to `http://localhost:8080`.
