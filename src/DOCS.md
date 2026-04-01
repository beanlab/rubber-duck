# `src/` Architecture

## Purpose

`src/` contains the runtime application for the Rubber Duck bot.
Each subdirectory owns a subsystem with a focused responsibility.

## Operational Flow

1. `main.py` parses CLI mode selection (`--platform discord|teams|both`) and loads adapter config(s).
2. Runtime composition is shared across adapters (SQL/session state, armory, AI client, ducks, workflow manager).
3. Adapter runtime starts:
   - Discord via `DiscordBot.start(...)`
   - Teams via aiohttp `/api/messages` + Bot Framework adapter
4. `RubberDuckApp` routes admin messages to `command` workflows and duck-channel messages to `duck-orchestrator` workflows.
5. `DuckOrchestrator` creates a thread-scoped `DuckContext`, runs the selected duck workflow, and queues conversation metadata for TA feedback.
6. Subsystems (`gen_ai`, `armory`, `workflows`, `metrics`, `storage`, `utils`) execute behavior and persistence for that workflow.

## Boundaries

- `main.py` owns wiring and dependency assembly.
- `bot/` owns transport adapters and message conversion.
- `conversation/` and `workflows/` own user-facing behavior.
- `gen_ai/` owns model/tool loop execution.
- `storage/` and `metrics/` own persistence and analytics.
- `utils/` owns cross-cutting infrastructure helpers.

## Failure Modes and Guardrails

- Runtime composition is centralized in `main.py`; update `DOCS.md` files when ownership moves to avoid drift.
- Test coverage is still narrow compared to subsystem breadth, so refactors should be validated by targeted manual checks.
