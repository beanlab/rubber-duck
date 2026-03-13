---
name: Tests Assistance
description: |
  Instructions for how to provide developer assistance for test coverage and validation workflow.
  If you are asked to help with unit tests in this repository, load this skill.
---

## Relevant File Locations

- `src/tests/test_sql_metric_handlers.py`
- `src/storage/sql_metrics.py`
- `src/main.py`

## Current Test Scope

- The active test module targets SQL metrics behavior:
  - message recording
  - usage recording
  - feedback recording
- Test code is async-oriented (`pytest.mark.asyncio`) and exercises `SQLMetricsHandler` methods.

## Test Entry Flow

- Tests live under `src/tests/`.
- Typical command:
  - `pytest -v --asyncio-mode=auto`
- For targeted runs:
  - `pytest -v --asyncio-mode=auto src/tests/test_sql_metric_handlers.py`

## What To Verify When Updating Tests

- Test method signatures and assertions match current handler APIs in `src/storage/sql_metrics.py`.
- Setup fixtures/session creation are valid for the chosen SQL backend (usually SQLite for local test runs).
- Any command/reporting behavior that depends on metrics tables stays compatible with the tested schema.
