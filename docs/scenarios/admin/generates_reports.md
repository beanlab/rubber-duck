# Generates Reports

## Purpose

Create metric reports.

---

# Context

The bot is running with reporter settings configured and admin command
routing available.

---

# Action

An operator sends a `!report` command in the configured admin channel.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `!report`, `!report help`, or `!report h` | Returns report help text. |
| Other valid report command form | Returns generated report images and/or text output. |
| Report-generation failure | Returns an explicit report-generation error message. |

---

# Outcome

Report commands return help, generated report output, or explicit
report-generation failure messages.

---

# Related Scenarios

- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
- [Exports metric tables](exports_metric_tables.md)
