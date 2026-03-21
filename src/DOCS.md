# `src/` Architecture Notes

## Purpose

`src/` contains the runtime application code for the Rubber Duck Discord system.
It is organized by subsystem so each folder has a clear ownership boundary.

## Subsystem Boundaries

- `armory/`: Tool registration, schema generation, and tool execution/caching.
- `bot/`: Discord transport adapter and event plumbing.
- `commands/`: Admin command parsing and execution.
- `conversation/`: Conversation types and thread setup flow.
- `gen_ai/`: OpenAI client calls and agent/tool loop orchestration.
- `metrics/`: Feedback workflows, metrics reporting, and analytics surfaces.
- `storage/`: SQL/session setup and persistence handlers.
- `utils/`: Shared infrastructure helpers (config, logging, queueing, execution helpers).
- `workflows/`: Multi-step product workflows (registration, assignment feedback).
- `tests/`: Targeted runtime tests (currently minimal coverage).

Each subsystem has its own `DOCS.md` with implementation details.

## End-to-End Runtime Flow

1. `main.py` loads config, initializes dependencies, and wires workflows.
2. `bot/discord_bot.py` receives Discord events.
3. `rubber_duck_app.py` routes events into quest workflows.
4. `duck_orchestrator.py` creates thread-scoped contexts and dispatches the selected duck/workflow.
5. Conversation/workflow modules call `gen_ai/` and `armory/` as needed.
6. `storage/` and `metrics/` persist state and usage/feedback records.

## Dependency Direction (Preferred)

- High-level wiring should stay in `main.py`.
- Transport (`bot/`) should not own business logic.
- Workflows/conversations may depend on `gen_ai/`, `metrics/`, `storage/`, and `utils/`.
- `utils/` should remain dependency-light and reusable.

## Potential Weak Points

- Test coverage is narrow (`src/tests/` is not yet representative of all subsystems).
- `main.py` has broad wiring responsibilities and can accumulate orchestration complexity.
- Some subsystem docs may drift as runtime wiring evolves; reconcile these docs when moving responsibilities.
