---
name: Src Assistance
description: |
  Instructions for how to provide developer assistance for high-level architecture across the `src/` codebase.
  If you are asked to navigate multiple subsystems or make cross-module changes, load this skill.
---

## Relevant File Locations

- `src/main.py`
- `src/rubber_duck_app.py`
- `src/duck_orchestrator.py`
- `src/armory/`
- `src/gen_ai/`
- `src/conversation/`
- `src/workflows/`
- `src/commands/`
- `src/metrics/`
- `src/storage/`
- `src/utils/`

## Runtime Entry Flow

- `src/main.py` is the composition root:
  - loads config
  - builds SQL/session-backed services
  - constructs armory + AI client + ducks
  - sets up workflow manager and Discord bot runtime
- `DiscordBot` forwards inbound Discord events to `RubberDuckApp`.
- `RubberDuckApp` routes messages/reactions into workflow types (`command`, `duck-orchestrator`, or existing thread workflow).
- `DuckOrchestrator` creates thread context and dispatches to channel-specific duck workflows/conversations.

## Source Area Map

- `armory/`: tool registration, schemas, talk tools, and tool caching.
- `gen_ai/`: agent config + OpenAI response/tool loop runtime.
- `conversation/`: agent-led and user-led conversation wrappers + thread setup.
- `workflows/`: registration and assignment-feedback domain workflows.
- `commands/`: admin command parsing and command implementations.
- `metrics/`: message/usage/feedback capture and report generation.
- `storage/`: SQL session setup and persistence adapters for workflow + metrics data.
- `utils/`: shared infra (config loading, types/protocols, logging, queues, containers, schedulers).
- `tests/`: repository test modules.
