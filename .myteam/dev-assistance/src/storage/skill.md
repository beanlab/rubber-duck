---
name: Storage Assistance
description: |
  Instructions for how to provide developer assistance for SQL sessions, workflow persistence, and metrics storage.
  If you are asked to help with database configuration or persistence behavior, load this skill.
---

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
