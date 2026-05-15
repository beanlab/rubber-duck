# Exports Logs

## Purpose

Export runtime logs.

---

# Context

The bot is running and admin command routing is available.

---

# Action

An operator sends `!log` in the configured admin channel.

---

# Interaction

| Action | Outcome |
| --- | --- |
| `!log` with configured log files | Returns a zip file containing logs. |
| `!log` without logging configured | Replies `Log export disabled: no log path configured.` |
| `!log` with no logs present | Returns a no-logs message. |

---

# Outcome

Log export commands either return available logs or explain why no log
export is available.

---

# Related Scenarios

- [Starts bot runtime](../startup/starts_bot_runtime.md)
- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
