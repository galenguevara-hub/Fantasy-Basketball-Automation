# Documentation Index

## Primary Docs

- `README.md`: repo overview, setup, routes, runtime behavior
- `docs/QUICKSTART.md`: shortest path to a working local install
- `docs/ARCHITECTURE.md`: runtime modes, data flow, and component responsibilities
- `docs/IMPLEMENTATION_SUMMARY.md`: current implementation and verification snapshot
- `docs/CHANGELOG.md`: documentation and behavior history

## Verification And Summary Notes

- `docs/FEATURE_VERIFICATION.txt`: what was checked against code on the latest docs pass
- `docs/UPDATES_SUMMARY.txt`: concise summary of the latest docs refresh
- `docs/FINAL_SUMMARY.txt`: final completion note for the latest docs refresh

## Frontend-Specific Doc

- `frontend/README.md`: React routes, backend contracts, dev/prod workflow

## Code References

- `src/fba/app.py`: Flask entrypoint and route definitions
- `src/fba/auth.py`: Yahoo OAuth and session handling
- `src/fba/yahoo_api.py`: Yahoo Fantasy API client
- `src/fba/normalize.py`: per-game normalization and re-ranking
- `src/fba/analysis/category_targets.py`: layer-1 target analysis
- `src/fba/analysis/cluster_leverage.py`: layer-2 cluster analysis
- `src/fba/analysis/games_played.py`: pace analysis
- `src/fba/scraper.py`: optional Playwright scraper
- `scripts/start_server.sh`: default local startup
- `scripts/start_dev.sh`: backend + Vite dev startup

## Current Verification Snapshot

As of March 1, 2026:

- pure calculation tests: `120 passed`
- full `./venv/bin/pytest -q` run is blocked in the checked-in `venv` until requirements are reinstalled there
