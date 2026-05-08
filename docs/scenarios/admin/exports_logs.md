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
| The operator sends `!log` while a logging path is configured and log files exist. | The application returns a zip file containing logs. |
| The operator sends `!log` while logging is not configured. | The application replies `Log export disabled: no log path configured.` |
| The operator sends `!log` while no logs are present. | The application returns a no-logs message. |

---

# Outcome

Log export commands either return available logs or explain why no log
export is available.

---

# Related Scenarios

- [Starts bot runtime](../startup/starts_bot_runtime.md)
- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
