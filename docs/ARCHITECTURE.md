# Architecture Overview

## Runtime Flow

```text
Browser (localhost:8080)
  -> Flask app (src/fba/app.py)
     -> reads/writes data/config.json
     -> reads data/standings.json
     -> serves JSON payloads for React frontend (`/api/overview`, `/api/analysis`, `/api/games-played`)
     -> serves React build assets from `frontend/dist` (mode-controlled via `FBA_UI_MODE`)
     -> POST /refresh runs scraper subprocess
          -> src/fba/scraper.py
             -> Yahoo standings page (Playwright)
             -> writes data/browser_state.json (login mode)
             -> writes data/standings.json
```

## Main Components

### `src/fba/app.py`

- Serves HTML pages:
  - `GET /`
  - `GET /analysis`
  - `GET /games-played`
- Serves API endpoints:
  - `GET /api/config`
  - `POST /api/config`
  - `GET /api/overview`
  - `GET /api/analysis`
  - `GET /api/games-played`
  - `GET /api/standings`
  - `POST /refresh`
- Calls:
  - `normalize_standings()`
  - `compute_gaps_and_scores()`
  - `compute_cluster_metrics()`
  - `compute_games_played_metrics()`

### `src/fba/scraper.py`

- Uses Playwright Chromium for Yahoo login/session.
- Uses BeautifulSoup to parse standings HTML tables.
- Supports:
  - `--league-id`
  - `--login`
  - `--no-prompt`
  - `--outfile`

### `src/fba/normalize.py`

- Builds per-game rows from raw stats.
- Builds per-category rank table.
- Current rank direction is: `N=best`, `1=worst`.

### `src/fba/analysis/category_targets.py`

- Computes per-category:
  - next better / next worse team
  - raw gap and z-score gap
  - target score: `1/z_gap_up + 0.25*z_gap_down`
- Applies tags:
  - top 3 by score -> `TARGET`
  - lowest 2 buffers (excluding targets) -> `DEFEND`

### `src/fba/analysis/cluster_leverage.py`

- Computes per-category cluster density and multi-point movement potential.
- Exposes:
  - `z_to_gain_1/2/3`
  - `z_to_lose_1/2/3`
  - `points_up_within_T`
  - `cluster_up_score`
  - `points_down_within_T`
  - `cluster_down_risk`
- Applies cluster tags:
  - top 3 by `cluster_up_score` -> `TARGET`
  - top 2 by `cluster_down_risk` (excluding targets) -> `DEFEND`

### `src/fba/analysis/games_played.py`

- Computes games-played pace metrics:
  - `avg_gp_per_day_so_far`
  - `avg_gp_per_day_needed`
  - `net_rate_delta`
- Uses configurable `start`, `end`, and `total_games`.
- Returns rows plus `date_valid` flag for UI validation messaging.

### Frontend

- Templates: `src/fba/templates/index.html`, `src/fba/templates/analysis.html`, `src/fba/templates/games_played.html`
- Static: `src/fba/static/app.js`, `src/fba/static/style.css`
- JS handles league config, refresh actions, and table sorting.
- React app: `frontend/` (Vite + React + TypeScript) consuming Flask JSON endpoints.
- UI mode switch (`FBA_UI_MODE`):
  - `react` (default): force React (returns 503 if build missing).
  - `legacy`: explicit compatibility mode for Jinja templates.
  - `auto`: compatibility alias for `react`.
- In React mode, Flask serves built `index.html` for `/`, `/analysis`, `/games-played` and bundle files under `/assets/*`.
- React table default sorting:
  - `/`: Per-Game Category Rankings by `rank_total` descending.
  - `/analysis`: Category Analysis by `target_score` descending.
  - `/analysis`: Cluster Leverage by `cluster_up_score` descending.
- React URL query-state:
  - `?team=<name>` for selected team on `/analysis`.
  - `?start=...&end=...&total_games=...` for `/games-played`.

## Data Files

- `data/config.json`: app config (currently league ID)
- `data/browser_state.json`: Playwright auth session
- `data/standings.json`: scraped standings payload
- `data/standings.csv`: present in repo data directory (not used by app routes)

## Legacy/Optional Component

- `src/fba/webhook_server.py` exists but references old scripts such as `yahoo_roto_standings.py` and `push_to_sheets.py` that are not in this repository.
- It is not used by `src/fba/app.py`.
