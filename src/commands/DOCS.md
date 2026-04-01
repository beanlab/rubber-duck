## Purpose

`src/commands` handles admin-channel command parsing and execution.

## Operational Flow

- `RubberDuckApp` starts workflow type `command` for admin-channel messages.
- `BotCommands.handle_command(...)` dispatches by first token (`content.split()[0]`).
- `!help` is generated dynamically from registered command objects.
- Unknown commands return `Unknown command. Try !help`.

## Dependencies

- Command creation/wiring is owned by `main.setup_workflow_manager(...)` through `create_commands(...)`.
- Data/report commands depend on `SQLMetricsHandler`, `Reporter`, and utility exporters.

## Failure Modes and Guardrails

- Dispatch exceptions are caught in `BotCommands` and return a generic error to the channel.
- Current built-ins include: `!messages`, `!usage`, `!feedback`, `!metrics`, `!status`, `!report`, `!log`, `!active`, and `!cache`.
- `!cache clear` requires explicit `confirm` suffix to avoid accidental destructive cleanup.
