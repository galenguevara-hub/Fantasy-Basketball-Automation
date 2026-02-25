# Changelog

## 2026-02-22

### Documentation synchronization

- Updated `README.md` and all files under `docs/` to match the current repository structure and behavior.
- Standardized commands to current paths (`src/fba/*`, `scripts/*`, `data/*`).
- Clarified active endpoints from `src/fba/app.py`.
- Clarified that `src/fba/webhook_server.py` is legacy/optional and not part of the main runtime flow.
- Removed outdated references to root-level scripts and old file paths.

### Behavior clarified in docs

- `normalize.py` rank direction documented as `N=best`, `1=worst`.
- Category targets analysis formula and tag assignment documented from current code.
- Current test result snapshot documented:
  - `./venv/bin/pytest -q` -> `40 passed, 4 failed`
  - Failing tests are rank-direction expectations in `tests/test_normalize.py`.
