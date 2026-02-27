# Changelog

## 2026-02-27

### React parity and behavior updates

- Restored React parity for legacy analysis and standings behavior:
  - analysis summary panel (`Categories to Target` / `Categories to Defend`)
  - full analysis comparison columns (`Better/Worse Team`, `Gap+`, `Gap−`, etc.)
  - games-played explanatory key block
  - standings per-game rankings table shape (`Rank`, `GP`, `Total`, `Delta Total`)
- Added URL query-state support in React:
  - `/analysis?team=...`
  - `/games-played?start=...&end=...&total_games=...`
- Set default React table sorts:
  - Per-Game Category Rankings: `Total` descending
  - Category Analysis: `Score` descending
  - Cluster Leverage: `Up Score` descending

### Test and regression coverage

- Added `tests/test_calculation_regression_parity.py` to verify:
  - legacy-route payloads and API payloads match for calculated fields
  - overview, analysis/cluster, and games-played formulas match expected calculations
- Current test snapshot:
  - `./venv/bin/pytest -q` -> `135 passed`

### Documentation refresh

- Updated `README.md` and docs under `docs/` to reflect current endpoints, behaviors, defaults, and test status.

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
