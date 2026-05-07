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

# Outcome

`!active` returns workflow counts by type. `!active full` returns
detailed active workflow entries with Mountain Time timestamps.

---

# Related Scenarios

- [Forwards active thread messages](../routing/forwards_active_thread_messages.md)
- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
