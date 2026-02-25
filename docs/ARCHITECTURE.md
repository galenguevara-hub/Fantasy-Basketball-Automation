# Architecture Overview

## Runtime Flow

```text
Browser (localhost:8080)
  -> Flask app (src/fba/app.py)
     -> reads/writes data/config.json
     -> reads data/standings.json
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
- Serves API endpoints:
  - `GET /api/config`
  - `POST /api/config`
  - `GET /api/standings`
  - `POST /refresh`
- Calls `normalize_standings()` and `compute_gaps_and_scores()`.

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

### Frontend

- Templates: `src/fba/templates/index.html`, `src/fba/templates/analysis.html`
- Static: `src/fba/static/app.js`, `src/fba/static/style.css`
- JS handles league config, refresh actions, and table sorting.

## Data Files

- `data/config.json`: app config (currently league ID)
- `data/browser_state.json`: Playwright auth session
- `data/standings.json`: scraped standings payload
- `data/standings.csv`: present in repo data directory (not used by app routes)

## Legacy/Optional Component

- `src/fba/webhook_server.py` exists but references old scripts such as `yahoo_roto_standings.py` and `push_to_sheets.py` that are not in this repository.
- It is not used by `src/fba/app.py`.
