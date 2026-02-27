# Documentation Index

## Primary Docs

- `README.md`: high-level overview, setup, commands, endpoints
- `docs/QUICKSTART.md`: minimal setup and first run
- `docs/ARCHITECTURE.md`: component and data-flow details
- `docs/CHANGELOG.md`: documentation and behavior updates
- `docs/IMPLEMENTATION_SUMMARY.md`: current implementation and test snapshot

## Practical References

- Main server: `src/fba/app.py`
- Scraper: `src/fba/scraper.py`
- Normalization: `src/fba/normalize.py`
- Category analysis: `src/fba/analysis/category_targets.py`
- Cluster analysis: `src/fba/analysis/cluster_leverage.py`
- Games played analysis: `src/fba/analysis/games_played.py`
- Startup script: `scripts/start_server.sh`
- Tests:
  - `tests/test_normalize.py`
  - `tests/test_category_targets.py`
  - `tests/test_cluster_leverage.py`
  - `tests/test_games_played.py`
  - `tests/test_app_api.py`
  - `tests/test_calculation_regression_parity.py`
