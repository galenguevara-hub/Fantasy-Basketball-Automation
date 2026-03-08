# Documentation Index

## Primary Docs

- `README.md`: repo overview, deployment model, and supported runtime path
- `docs/QUICKSTART.md`: local shell, Docker Compose, and Fly.io startup path
- `docs/ARCHITECTURE.md`: runtime flow, Redis keying/TTL behavior, and
  deployment topology
- `docs/IMPLEMENTATION_SUMMARY.md`: active endpoints, runtime behavior, and
  analysis-layer semantics
- `docs/CHANGELOG.md`: recent repo, deployment, and docs changes

## Frontend Doc

- `frontend/README.md`: route behavior, API contracts, analysis UI semantics,
  and Docker/Fly frontend packaging

## Archive Doc

- `legacy/README.md`: what was moved out of the supported path and why

## Deployment References

- `Dockerfile`: production image definition
- `.dockerignore`: image exclusions
- `docker-compose.yml`: local Docker + Redis stack
- `fly.toml`: Fly.io app definition
- `.env.example`: current environment variable template

## Code References

- `src/fba/app.py`: Flask entrypoint, session config, and cache integration
- `src/fba/auth.py`: Yahoo OAuth and session handling
- `src/fba/yahoo_api.py`: Yahoo Fantasy API client
- `src/fba/normalize.py`: per-game normalization and re-ranking
- `src/fba/analysis/category_targets.py`: layer-1 target/defend scoring
- `src/fba/analysis/cluster_leverage.py`: layer-2 cluster leverage scoring (v2
  active, v1 retained)
- `src/fba/analysis/games_played.py`: pace analysis
- `src/fba/analysis/executive_summary.py`: cross-model synthesis for the
  executive summary dashboard
- `scripts/start_server.sh`: default local startup
- `scripts/start_dev.sh`: backend + Vite dev startup

## Current Verification Snapshot

Latest recorded (March 8, 2026):

- maintained calculation tests: `78 passed`
- frontend production build: passed
- full `./venv/bin/pytest -q` is still blocked in the checked-in `venv`
  because backend packages are missing there
- Docker/Fly config was validated from checked-in files, not exercised live in
  that pass
