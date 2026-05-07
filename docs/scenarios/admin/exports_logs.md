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

# Outcome

If a logging path is configured and log files exist, the application
returns a zip file containing logs. If logging is not configured, the
application replies `Log export disabled: no log path configured.` If no
logs are present, the application returns a no-logs message.

---

# Related Scenarios

- [Starts bot runtime](../startup/starts_bot_runtime.md)
- [Routes admin channel messages to commands](../routing/routes_admin_channel_messages_to_commands.md)
