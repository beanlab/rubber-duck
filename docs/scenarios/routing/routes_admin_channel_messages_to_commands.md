# Routes Admin Channel Messages To Commands

## Purpose

Handle operator commands.

---

# Context

The bot is running and an admin channel is configured.

---

# Action

A non-bot Discord message is posted in the configured admin channel.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Non-bot admin-channel message | Treats the message as an admin command. |
| `!help` | Returns a generated help list of registered commands. |
| Unknown command | Returns `Unknown command. Try !help`. |
| Command execution error | Returns a generic unexpected-error message instead of exposing an unhandled exception to Discord users. |

---

# Outcome

Admin-channel messages are handled through the admin command interface,
including help, unknown-command, and command-error responses.

---

# Related Scenarios

- [Reports status](../admin/reports_status.md)
- [Exports metric tables](../admin/exports_metric_tables.md)
- [Generates reports](../admin/generates_reports.md)
- [Exports logs](../admin/exports_logs.md)
- [Reports active conversations](../admin/reports_active_conversations.md)
- [Manages cache entries](../admin/manages_cache_entries.md)
