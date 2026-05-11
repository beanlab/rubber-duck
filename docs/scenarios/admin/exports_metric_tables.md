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
| `!messages` | Returns a zip file export for message telemetry. |
| `!usage` | Returns a zip file export for usage telemetry. |
| `!feedback` | Returns a zip file export for feedback telemetry. |
| `!metrics` | Returns all message, usage, and feedback table exports. |

---

# Outcome

Metric export commands return the requested telemetry table exports as
Discord file responses.

---

# Related Scenarios

- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
- [Conversation review scores queued conversations](../conversation_review/conversation_review_scores_queued_conversations.md)
