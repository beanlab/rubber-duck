## Relevant File Locations

- `src/storage/sql_connection.py`
- `src/storage/sql_quest.py`
- `src/storage/sql_metrics.py`
- `src/main.py`
- `src/metrics/reporter.py`

## Runtime Entry Flow

- `main._main(...)` creates a SQLAlchemy session via `create_sql_session(config['sql'])`.
- The same session is used for:
  - workflow manager persistence (`create_sql_manager(...)`)
  - metrics persistence (`SQLMetricsHandler`)
  - optional tool cache persistence (`SqlToolCache` in armory)
- Feedback queue persistence uses SQL-backed blob storage.

## SQL Session Construction

- `create_sql_session(...)` resolves `env:` values and supports:
  - SQLite (`sqlite:///...`) for local development
  - server databases via `db_type/username/password/host/port/database`
- For non-SQLite backends, `_create_sql_session(...)` attempts `CREATE DATABASE` before connecting to the target DB.

## Workflow and Queue Persistence

- `create_sql_manager(...)` builds quest `WorkflowManager` with SQL-backed `SqlBlobStorage`.
- `SqlBlobStorage` stores workflow blobs in `records` table keyed by namespace + key.
- Each workflow history uses its own SQL blob namespace (`wid`).

## Local Storage Fork Notes

- The repository currently has two `SqlBlobStorage` implementations in active runtime paths:
  - `src/storage/sql_quest.py::SqlBlobStorage` (used by `create_sql_manager(...)`)
  - `quest.extras.sql.SqlBlobStorage` (imported in `src/main.py` for feedback queues)
- The local implementation in `src/storage/sql_quest.py` is kept intentionally for workflow-manager paths because it
  updates records by `(name, key)` and aligns with this project's queue/history keying model.
- Migration to a single upstream storage implementation should only happen after all of the following are true:
  - upstream write/update semantics are verified equivalent for `(name, key)` behavior used by this project
  - a regression test exists that covers multiple keys under a shared namespace
  - workflow history and queue persistence are both validated against the same storage backend

## Metrics Persistence

- `SQLMetricsHandler` defines and creates SQL tables:
  - `messages`
  - `usage`
  - `feedback`
- Runtime writers:
  - `record_message(...)`
  - `record_usage(...)`
  - `record_feedback(...)`
- Read paths (`get_messages/get_usage/get_feedback`) return list-shaped table exports for reporting/commands.
