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

## Current Test Status

- Test coverage is currently minimal and not representative of the full system.
- Existing tests are limited to early SQL metrics coverage and may not match current implementations.
- Most modules (bot, conversation, workflows, gen_ai, armory, utils) do not yet have dedicated tests.

## Test Entry Flow

- Tests live under `src/tests/`.
- Typical command:
  - `pytest -v --asyncio-mode=auto`
- For targeted runs:
  - `pytest -v --asyncio-mode=auto src/tests/test_sql_metric_handlers.py`

## Guidance For Contributors

- When changing behavior, add targeted tests in the same area first.
- Prioritize tests for:
  - message routing and workflow dispatch
  - armory tool registration/schema generation
  - AI/tool loop behavior with mocked model responses
  - registration and assignment-feedback workflow paths
- Keep tests isolated from external services (Discord/OpenAI/S3) using mocks or stubs.
