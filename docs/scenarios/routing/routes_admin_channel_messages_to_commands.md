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
| A non-bot Discord message is posted in the configured admin channel. | The application treats the message as an admin command. |
| The message is `!help`. | The application returns a generated help list of registered commands. |
| The message names an unknown command. | The application returns `Unknown command. Try !help`. |
| Command execution raises an error. | The application returns a generic unexpected-error message instead of exposing an unhandled exception to Discord users. |

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
- [Reports active workflows](../admin/reports_active_workflows.md)
- [Manages cache entries](../admin/manages_cache_entries.md)
