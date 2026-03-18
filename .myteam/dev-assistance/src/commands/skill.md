---
name: Commands Assistance
description: |
  Instructions for how to provide developer assistance for admin command parsing and execution.
  If you are asked to help with command behavior, command wiring, or command output flow, load this skill.
---

## Relevant File Locations

- `src/commands/bot_commands.py`
- `src/commands/command.py`
- `src/main.py`
- `src/rubber_duck_app.py`

## Runtime Entry Flow

- `RubberDuckApp.route_message(...)` routes admin-channel messages into workflow type `command`.
- `main.setup_workflow_manager(...)` wires `BotCommands` as the `command` workflow handler.
- `main.create_commands(...)` builds command instances and passes them into `BotCommands`.

## Command Dispatch Flow

- `BotCommands.handle_command(...)` parses `content.split()[0]` as the command name.
- `!help` is handled directly by `BotCommands.get_help(...)`.
- Known commands are looked up by name and executed via `command.execute(message)`.
- Unknown commands return `Unknown command. Try !help`.

## Built-In Command Set

- Metrics export:
  - `!messages`, `!usage`, `!feedback`, `!metrics`
- Bot/runtime checks:
  - `!status`, `!active` (`full` option for detailed active workflows)
- Reporting/logging:
  - `!report`, `!log`

## Command Output Behavior

- Most commands respond with `send_message(channel_id, ...)` text and/or Discord files.
- Metrics commands generate zipped files via `zip_data_file(...)`.
- `ReportCommand` returns help text, messages, or generated image files depending on input.
- `LogCommand` zips `*.log*` files from configured `log_dir` before sending.
