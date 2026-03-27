# `src/` Architecture

## Purpose

`src/` contains the runtime application for the Rubber Duck Discord bot.
Each subdirectory owns a subsystem with a focused responsibility.

## Operational Flow

1. `main.py` loads config, initializes SQL/session state, and builds runtime dependencies.
2. `DiscordBot` receives Discord events and forwards them to `RubberDuckApp`.
3. `RubberDuckApp` routes admin messages to `command` workflows and duck-channel messages to `duck-orchestrator` workflows.
4. `DuckOrchestrator` creates a thread-scoped `DuckContext`, runs the selected duck workflow, and queues conversation metadata for TA feedback.
5. Subsystems (`gen_ai`, `armory`, `workflows`, `metrics`, `storage`, `utils`) execute behavior and persistence for that workflow.

## Boundaries

- `main.py` owns wiring and dependency assembly.
- `bot/` owns Discord transport and message conversion.
- `conversation/` and `workflows/` own user-facing behavior.
- `gen_ai/` owns model/tool loop execution.
- `storage/` and `metrics/` own persistence and analytics.
- `utils/` owns cross-cutting infrastructure helpers.

## Failure Modes and Guardrails

- Runtime composition is centralized in `main.py`; update `DOCS.md` files when ownership moves to avoid drift.
- Test coverage is still narrow compared to subsystem breadth, so refactors should be validated by targeted manual checks.
