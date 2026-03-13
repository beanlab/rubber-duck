---
name: Bot Assistance
description: |
  Instructions for how to provide developer assistance for Discord bot runtime and message routing.
  If you are asked to help with Discord integration, channel routing, or bot event flow, load this skill.
---

## Relevant File Locations

- `src/bot/discord_bot.py`
- `src/rubber_duck_app.py`
- `src/main.py`
- `src/duck_orchestrator.py`
- `src/commands/bot_commands.py`

## Runtime Entry Flow

- `main._main(...)` builds `DiscordBot`, `RubberDuckApp`, and workflow manager, then starts the bot with `bot.start(os.environ['DISCORD_TOKEN'])`.
- `DiscordBot.set_duck_app(...)` wires the bot transport to the app router.
- `DiscordBot.on_ready(...)` sends a startup message to admin channel.

## Message and Reaction Routing

- `DiscordBot.on_message(...)` filters bot/self messages and `//`-prefixed messages, then forwards to `RubberDuckApp.route_message(...)`.
- `RubberDuckApp.route_message(...)` routes by channel:
  - admin channel -> starts `command` workflow
  - configured duck channel -> starts `duck-orchestrator` workflow
  - existing conversation thread -> sends event into active workflow
- `DiscordBot.on_reaction_add(...)` forwards emoji events to `RubberDuckApp.route_reaction(...)`, which maps reactions to workflow feedback events.

## Discord Transport Behavior

- `send_message(...)` supports text, single/multiple files, and Discord views; returns created message id.
- Long text is split by `_parse_blocks(...)` with code-fence-aware chunking.
- Files are normalized by `_make_discord_file(...)` from tuple/dict/`discord.File`.
- `typing(channel_id)` provides async typing context for model calls.
