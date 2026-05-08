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
| The operator sends `!report`, `!report help`, or `!report h`. | The application returns report help text. |
| The operator sends another valid report command form. | The application returns generated report images and/or text output. |
| Report generation fails. | The application returns an explicit report-generation error message. |

---

# Outcome

Report commands return help, generated report output, or explicit
report-generation failure messages.

---

# Related Scenarios

- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
- [Exports metric tables](exports_metric_tables.md)
