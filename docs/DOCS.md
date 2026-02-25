# Documentation Index

## Primary Docs

- `README.md`: high-level overview, setup, commands, endpoints
- `docs/QUICKSTART.md`: minimal setup and first run
- `docs/ARCHITECTURE.md`: component and data-flow details
- `docs/CHANGELOG.md`: documentation and behavior updates

## Supplemental Project Notes

- `docs/IMPLEMENTATION_SUMMARY.md`
- `docs/FEATURE_VERIFICATION.txt`
- `docs/FINAL_SUMMARY.txt`
- `docs/UPDATES_SUMMARY.txt`

These supplemental files now describe the current implementation and highlight where older assumptions no longer match current behavior.

## Practical References

- Main server: `src/fba/app.py`
- Scraper: `src/fba/scraper.py`
- Normalization: `src/fba/normalize.py`
- Category analysis: `src/fba/analysis/category_targets.py`
- Startup script: `scripts/start_server.sh`
- Tests: `tests/test_normalize.py`, `tests/test_category_targets.py`
