## Purpose

`src/bot` is the Discord transport adapter. It converts Discord events into internal protocol objects and sends messages/files/reactions back to Discord.

## Operational Flow

- `DiscordBot.on_message(...)` ignores bot/self messages and `//`-prefixed messages, then forwards normalized messages to `RubberDuckApp.route_message(...)`.
- `DiscordBot.on_reaction_add(...)` forwards reaction events to `RubberDuckApp.route_reaction(...)`.
- `on_ready(...)` announces startup in the configured admin channel.
- Outbound calls use `send_message(...)`, `add_reaction(...)`, `typing(...)`, and `create_thread(...)`.

## Dependencies

- Depends on `discord.py` for transport.
- Depends on routing logic in `src/rubber_duck_app.py`.

## Failure Modes and Guardrails

- `send_message(...)` raises if text/file/view is missing or if the channel cannot be resolved.
- Long text output is chunked with code-fence-aware splitting, so formatting-sensitive responses should still be reviewed when changing `_parse_blocks(...)`.
