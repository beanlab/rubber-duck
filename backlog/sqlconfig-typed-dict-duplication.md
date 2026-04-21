# SqlConfig TypedDict Duplication

Created on: 2026-04-20
Created by: Tyler (discovered by spring-cleaning agents)

## Details

There are two `SqlConfig`/`SQLConfig` TypedDict definitions, and the one
referenced by `Config` does not match sqlite-only runtime usage. This can hide
config drift or mislead future changes.

- Problem addressed: duplicate config type definitions with conflicting fields.
- Intent: unify `SqlConfig` type usage so sqlite and non-sqlite shapes are
  represented consistently.
- Known details:
  - `src/utils/config_types.py` defines `SQLConfig` with required
    `username/password/host/port` fields.
  - `src/storage/sql_connection.py` defines a separate `SqlConfig` and
    `create_sql_session` branches on `db_type == 'sqlite'` using only `database`.

## Out-of-scope

- Changing database connection behavior without a design pass.
- Expanding config validation beyond TypedDict cleanup.

## Dependencies

- None noted.
