# Reports Active Workflows

## Purpose

Inspect running workflows.

---

# Context

The bot is running and may have active duck workflows.

---

# Action

An operator sends `!active` or `!active full` in the configured admin
channel.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `!active` | Returns active workflow counts by type. |
| `!active full` | Returns detailed active workflow entries with Mountain Time timestamps. |

---

# Outcome

Active workflow commands report the currently running workflows at the
requested level of detail.

---

# Related Scenarios

- [Forwards active thread messages](../routing/forwards_active_thread_messages.md)
- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
