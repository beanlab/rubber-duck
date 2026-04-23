## Purpose

`tests/` currently provides lightweight regression checks for a narrow slice of
the stats-oriented tooling path.

## Operational Flow

- `test_sql_metric_handlers.py` validates insert/read paths for `messages`, `usage`, and `feedback` via in-memory SQLite.
- `test_dataset_tools.py` validates dataset list ordering and deduplication in
  the stats-oriented tooling path.
- `conftest.py` injects a minimal `quest` module shim so tests can import project modules without full runtime dependencies.

## Failure Modes and Guardrails

- Test coverage is intentionally narrow; most runtime subsystems are currently untested in this directory.
- The remaining coverage is still implementation-adjacent and does not yet map
  cleanly to most of the black-box contract in `docs/application_interface.md`.
- These tests do not yet cover most of the black-box Discord and startup
  contract defined in `docs/application_interface.md`.
