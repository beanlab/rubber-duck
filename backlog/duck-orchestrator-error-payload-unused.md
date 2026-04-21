# Duck Orchestrator Error Payload Unused

Created on: 2026-04-20
Created by: Tyler (discovered by spring-cleaning agents)

## Details

`generate_error_message` in `src/duck_orchestrator.py` builds a full error payload
that is never sent to users; only the error code is emitted. This creates an
unused data path and can confuse the intended error-handling behavior.

- Problem addressed: error payload data is computed but not used.
- Intent: decide whether to surface the full error message (e.g., in debug mode)
  or simplify the function to return only the error code.
- Known details:
  - Exception handler currently sends only `error_code`.
  - `generate_error_message` returns `(error_message, error_code)`.

## Out-of-scope

- Changing error-handling behavior without a dedicated design pass.
- Adding new user-visible error messaging.

## Dependencies

- None noted.
