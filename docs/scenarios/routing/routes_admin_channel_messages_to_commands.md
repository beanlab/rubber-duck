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

# Outcome

The application treats the message as an admin command.

`!help` returns a generated help list of registered commands. Unknown
commands return `Unknown command. Try !help`. Command execution errors
return a generic unexpected-error message instead of exposing an
unhandled exception to Discord users.

---

# Related Scenarios

- [Reports status](../admin/reports_status.md)
- [Exports metric tables](../admin/exports_metric_tables.md)
- [Generates reports](../admin/generates_reports.md)
- [Exports logs](../admin/exports_logs.md)
- [Reports active workflows](../admin/reports_active_workflows.md)
- [Manages cache entries](../admin/manages_cache_entries.md)
