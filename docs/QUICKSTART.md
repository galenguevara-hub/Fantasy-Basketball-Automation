# Quick Start

## 1) Local Install

```bash
cd "/Users/galen/projects/Fantasy Basketball Automation"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend install
cp .env.example .env
```

Set at minimum:

- `SECRET_KEY`
- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `REDIS_URL` for the current multi-user React refresh flow

Recommended:

- `TOKEN_ENCRYPTION_KEY`

## 2) Build The UI

```bash
npm --prefix frontend run build
```

## 3) Start The App (Local Shell)

```bash
./scripts/start_server.sh
```

Open `http://localhost:8080`.

For the current React flow, this shell path expects a working Redis instance
behind `REDIS_URL`. If you do not already have Redis running, use Docker
Compose instead.

Without `REDIS_URL`, the app still starts but refreshed standings are not
persisted for React API reads.

## 4) Start The App (Docker Compose)

For the new production-like local stack with Redis:

```bash
docker compose up --build
```

This starts:

- the app container on `http://localhost:8080`
- Redis on `localhost:6379`

Compose injects:

- `REDIS_URL=redis://redis:6379/0`
- `FBA_UI_MODE=react`
- `YAHOO_REDIRECT_URI=http://localhost:8080/auth/yahoo/callback`

You still need `YAHOO_CLIENT_ID` and `YAHOO_CLIENT_SECRET` in your environment.
This is currently the simplest fully working local path because it wires Redis
automatically.

## 5) Connect A League

1. Enter your Yahoo league ID.
2. Click `Connect`.
3. Complete Yahoo OAuth if prompted.
4. The app refreshes standings through the Yahoo Fantasy API.

Notes:

- refresh is rate-limited per user to one request every 30 seconds when Redis
  is enabled
- on rate limit, the API returns `429` with `retry_after`, and the UI shows a
  countdown

## 6) Frontend Dev Mode

```bash
./scripts/start_dev.sh
```

- React app: `http://localhost:5173`
- Flask API: `http://localhost:8080`

Vite proxies `/api`, `/refresh`, `/auth`, and `/logout` to the Flask backend.

## 7) Fly.io Deploy Checklist

1. Keep `fly.toml` as the source of truth for the app definition.
2. Provision Redis and capture its `REDIS_URL`.
3. Set production secrets:
   `SECRET_KEY`, `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`,
   `YAHOO_REDIRECT_URI`, `TOKEN_ENCRYPTION_KEY`, and `REDIS_URL`.
4. Deploy with the Fly CLI using the checked-in `fly.toml`.

Current `fly.toml` highlights:

- app: `roto-fantasy-solver`
- region: `ord`
- VM: `shared-cpu-1x`, `256mb`
- min running machines: `1`
- health check: `GET /api/auth/status`

## 8) Verification

Latest recorded verification (March 3, 2026):

```bash
./venv/bin/pytest -q tests/test_normalize.py tests/test_category_targets.py tests/test_cluster_leverage.py tests/test_games_played.py
npm --prefix frontend run build
```

Results:

- pytest subset: `120 passed`
- frontend build: passed

If `./venv/bin/pytest -q` fails during collection, reinstall backend
dependencies inside `venv`:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

## 9) Legacy Tools

Deprecated tooling was moved to `legacy/`. It is not part of the supported app
or deployment path.
