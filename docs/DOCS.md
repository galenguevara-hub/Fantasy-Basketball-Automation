# Documentation Index

## Primary Docs

- `README.md`: repo overview, setup, routes, and supported runtime path
- `docs/QUICKSTART.md`: shortest path to a working local install
- `docs/ARCHITECTURE.md`: runtime modes, data flow, and module responsibilities
- `docs/IMPLEMENTATION_SUMMARY.md`: current implementation and verification
- `docs/CHANGELOG.md`: repo and docs cleanup history

## Frontend Doc

- `frontend/README.md`: React routes, backend contracts, and build/dev workflow

## Archive Doc

- `legacy/README.md`: what was moved out of the supported path and why

## Code References

- `src/fba/app.py`: Flask entrypoint and route definitions
- `src/fba/auth.py`: Yahoo OAuth and session handling
- `src/fba/yahoo_api.py`: Yahoo Fantasy API client
- `src/fba/normalize.py`: per-game normalization and re-ranking
- `src/fba/analysis/category_targets.py`: layer-1 target analysis
- `src/fba/analysis/cluster_leverage.py`: layer-2 cluster analysis
- `src/fba/analysis/games_played.py`: pace analysis
- `scripts/start_server.sh`: default local startup
- `scripts/start_dev.sh`: backend + Vite dev startup

## Current Verification Snapshot

As of March 1, 2026:

- maintained calculation tests: `120 passed`
- full `./venv/bin/pytest -q` is still blocked in the checked-in `venv` until
  backend requirements are reinstalled
