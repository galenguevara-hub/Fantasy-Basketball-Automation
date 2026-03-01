# Quick Start

## 1) Install

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend install
cp .env.example .env
```

Set in `.env`:

- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `SECRET_KEY`

Recommended:

- `TOKEN_ENCRYPTION_KEY`

## 2) Build The UI

```bash
npm --prefix frontend run build
```

## 3) Start The App

```bash
./scripts/start_server.sh
```

Open `http://localhost:8080`.

## 4) Connect A League

1. Enter your Yahoo league ID.
2. Click `Connect`.
3. Complete Yahoo OAuth if prompted.
4. The app refreshes standings through the Yahoo Fantasy API.

## 5) Frontend Dev Mode

```bash
./scripts/start_dev.sh
```

- React app: `http://localhost:5173`
- Flask API: `http://localhost:8080`

Vite proxies `/api`, `/refresh`, `/auth`, and `/logout` to the Flask backend.

## 6) Verification

```bash
./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py
```

Result on March 1, 2026: `120 passed`

If `./venv/bin/pytest -q` fails during collection, reinstall backend
dependencies inside `venv`:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

## 7) Legacy Tools

Deprecated tooling was moved to `legacy/`. It is not part of the supported app
path.
