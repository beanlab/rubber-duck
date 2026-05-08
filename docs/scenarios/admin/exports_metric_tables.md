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

# Interaction

| Action | Outcome |
| --- | --- |
| The operator sends `!messages`. | The application returns a zip file export for message telemetry. |
| The operator sends `!usage`. | The application returns a zip file export for usage telemetry. |
| The operator sends `!feedback`. | The application returns a zip file export for feedback telemetry. |
| The operator sends `!metrics`. | The application returns all message, usage, and feedback table exports. |

---

# Outcome

Metric export commands return the requested telemetry table exports as
Discord file responses.

---

# Related Scenarios

- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
- [Records reaction-based scores](../conversation_review/records_reaction_based_scores.md)
