## Purpose

`src/storage` provides SQL-backed persistence for workflow state and metrics.

## Operational Flow

- `create_sql_session(...)` builds a SQLAlchemy session from config (`env:` values are resolved before connect).
- `create_sql_manager(...)` builds the quest `WorkflowManager` with SQL-backed blob storage and per-workflow persistent history.
- `SQLMetricsHandler` creates and writes the `messages`, `usage`, and `feedback` tables and exposes read methods for reporting/exports.

## Dependencies

- Runtime wiring in `main.py` shares one SQL session across workflow storage, metrics, and optional SQL tool cache.
- Feedback queues use `quest.extras.sql.SqlBlobStorage` in `main._build_feedback_queues(...)`.

## Failure Modes and Guardrails

- Non-SQLite connection path attempts `CREATE DATABASE` before opening the target DB; permission issues fail startup.
- Workflow storage currently uses local `src/storage/sql_quest.py::SqlBlobStorage`, while feedback queues use `quest.extras.sql.SqlBlobStorage`; changing either path requires regression checks for key/update semantics.
