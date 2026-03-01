# Quick Start

## 1) Install Dependencies

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend install
cp .env.example .env
```

Set these in `.env` before using live Yahoo refresh:

- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`

Recommended for anything beyond throwaway local use:

- `SECRET_KEY`
- `TOKEN_ENCRYPTION_KEY`

## 2) Build The React UI

Default app mode is `react`, so build the frontend before starting Flask:

```bash
npm --prefix frontend run build
```

## 3) Start The App

```bash
./scripts/start_server.sh
```

Open `http://localhost:8080`.

## 4) Connect Your League

1. Enter your Yahoo league ID.
2. Click `Connect`.
3. If you are not signed in yet, the app redirects you to Yahoo via `/auth/yahoo`.
4. Complete Yahoo OAuth and return to the app.
5. The app fetches standings through the Yahoo Fantasy API and stores them in memory for the current session.

If Yahoo shows a code instead of redirecting cleanly, use the manual fallback endpoint handled by `POST /auth/code`.

## 5) React Development Mode (Optional)

Run Flask and Vite together:

```bash
./scripts/start_dev.sh
```

This starts:

- React app: `http://localhost:5173`
- Flask API: `http://localhost:8080`

In the current Vite config, only `/api` and `/refresh` are proxied. For Yahoo login/logout during development, use the Flask-served app at `http://localhost:8080` or add proxy rules for `/auth` and `/logout`.

## 6) Legacy / Manual Flows (Optional)

Serve the older Jinja templates instead of React:

```bash
FBA_UI_MODE=legacy ./scripts/start_server.sh
```

Use the file-based Yahoo OAuth helper:

```bash
PYTHONPATH=src ./venv/bin/python -m fba.oauth_setup --check
```

Use the Playwright scraper (not part of `POST /refresh`):

```bash
./venv/bin/pip install playwright
./venv/bin/playwright install chromium
PYTHONPATH=src ./venv/bin/python src/fba/scraper.py --login --league-id <LEAGUE_ID>
```

The scraper writes `data/standings.json` and `data/browser_state.json`.

## 7) Verification

Verified on March 1, 2026:

```bash
./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py
```

Result: `120 passed`

If `./venv/bin/pytest -q` fails during collection, reinstall backend dependencies inside `venv`:

```bash
source venv/bin/activate
pip install -r requirements.txt
```
