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

# Outcome

`!report`, `!report help`, and `!report h` return report help text.
Other valid report command forms return generated report images and/or
text output. Report-generation failures return an explicit
report-generation error message.

---

# Related Scenarios

- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
- [Exports metric tables](exports_metric_tables.md)
