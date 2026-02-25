# Implementation Summary

Status: current as of February 22, 2026.

## What is implemented

- Web app server in `src/fba/app.py`.
- Yahoo standings scraper in `src/fba/scraper.py`.
- Per-game normalization in `src/fba/normalize.py`.
- Category target analysis in `src/fba/analysis/category_targets.py`.
- Frontend templates and static assets under `src/fba/templates/` and `src/fba/static/`.

## Current file structure highlights

- Source code: `src/fba/`
- Tests: `tests/`
- Scripts: `scripts/`
- Runtime data: `data/`
- Config/examples: `config/`, `oauth2.json.example`, `google_credentials.json.example`

## Active endpoints (`src/fba/app.py`)

- `GET /`
- `GET /analysis`
- `POST /refresh`
- `GET /api/standings`
- `GET /api/config`
- `POST /api/config`

## Important behavior details

- Rankings from `normalize.py` use `N=best`, `1=worst`.
- `refresh` triggers `src/fba/scraper.py` via subprocess.
- If saved session is missing, refresh runs scraper login mode (`--login --no-prompt`).
- Standings and app config are JSON files under `data/`.

## Test snapshot

Running `./venv/bin/pytest -q` currently yields:

- 40 passing tests
- 4 failing tests in `tests/test_normalize.py`

The 4 failures are due to expected rank direction in those tests not matching current `normalize.py` behavior.
