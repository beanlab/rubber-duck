---
name: Utils Assistance
description: |
  Instructions for how to provide developer assistance for shared utility modules across config, logging, queues, and execution helpers.
  If you are asked to help with cross-cutting infrastructure behavior, load this skill.
---

## Relevant File Locations

- `src/utils/config_loader.py`
- `src/utils/config_types.py`
- `src/utils/protocols.py`
- `src/utils/logger.py`
- `src/utils/persistent_queue.py`
- `src/utils/cache_cleaner.py`
- `src/utils/feedback_notifier.py`
- `src/utils/python_exec_container.py`
- `src/utils/resource_staging.py`
- `src/utils/zip_utils.py`

## Runtime Entry Flow

- `main.py` depends on utils for:
  - config load + typed config contracts
  - logging and log forwarding to admin channel
  - persistent feedback queues
  - containerized code execution resources
  - background schedulers (cache cleaner, feedback notifier)

## Config and Type Contracts

- `config_loader.py` loads local/S3 config files and resolves `$include` directives with deep merge and JSONPath support.
- `config_types.py` defines TypedDict/dataclass contracts for top-level config, ducks, channels, containers, cache, and reporter settings.
- `protocols.py` defines shared interfaces (`SendMessage`, `AddReaction`, `ToolCache`, `CacheKeyBuilder`, etc.) used across modules.

## Logging and Queue Utilities

- `logger.py` configures `duck_logger`/`quest_logger`, file+console handlers, and async admin-channel log forwarding.
- `persistent_queue.py` provides SQL/blob-backed queue semantics (`put`, `pop`, persistence on context exit).
- `zip_utils.py` converts table-like data into zipped CSV payloads used by command outputs.

## Execution and Scheduling Utilities

- `python_exec_container.py` manages Docker container lifecycle, resource staging, isolated code execution, and output file extraction.
- `resource_staging.py` handles local/S3 dataset metadata and bytes retrieval for container resources.
- `cache_cleaner.py` schedules daily `ToolCache.cleanup()` runs.
- `feedback_notifier.py` schedules periodic pending-feedback notifications to TA channels.
