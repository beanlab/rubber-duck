## Purpose

`src/utils` contains shared infrastructure used across runtime subsystems.

## Operational Flow

- `config_loader.py` loads local/S3 JSON/YAML config and resolves recursive `$include` directives with deep-merge + JSONPath support.
- `logger.py` sets structured log formatting and optional admin-channel log forwarding.
- `persistent_queue.py` provides context-managed queue persistence backed by blob storage.
- `python_exec_container.py` manages Docker container lifecycle, resource staging, code execution, and artifact extraction.
- `cache_cleaner.py` and `feedback_notifier.py` run scheduled maintenance/notification loops.
- `zip_utils.py` exports table-like data as zipped CSV for command responses.

## Boundaries

- Utility modules should remain reusable and avoid owning product workflow decisions.
- Runtime orchestration and dependency assembly belong in `main.py`, not utility modules.

## Failure Modes and Guardrails

- Docker-dependent execution fails fast when daemon connectivity is unavailable.
- Queue persistence requires entering/exiting `PersistentQueue` contexts to rehydrate/stash state correctly.
- Config include cycles are rejected during load.
