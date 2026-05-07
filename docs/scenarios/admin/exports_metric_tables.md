# Exports Metric Tables

## Purpose

Export telemetry.

---

# Context

The bot is running with SQL-backed message, usage, and feedback
telemetry available through admin command routing.

---

# Action

An operator sends `!messages`, `!usage`, `!feedback`, or `!metrics` in
the configured admin channel.

---

# Outcome

`!messages`, `!usage`, and `!feedback` each return a zip file export for
their respective table. `!metrics` returns all three table exports.

---

# Related Scenarios

- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
- [Records reaction-based scores](../conversation_review/records_reaction_based_scores.md)
