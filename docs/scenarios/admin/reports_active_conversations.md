# Reports Active Conversations

## Purpose

Inspect active work.

---

# Context

The bot is running and may have active conversations or background jobs.

---

# Action

An operator sends `!active` or `!active full` in the configured admin
channel.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `!active` | Returns active conversation or job counts by kind. |
| `!active full` | Returns detailed active conversation or job entries with Mountain Time timestamps. |

---

# Outcome

Active-work commands report currently running conversations or jobs at
the requested level of detail.

---

# Related Scenarios

- [Forwards active thread messages](../routing/forwards_active_thread_messages.md)
- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
