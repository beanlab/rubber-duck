# Rejects Invalid Runtime Configuration

## Purpose

Surface startup failures.

---

# Context

An operator starts the application with missing, malformed, or invalid
runtime configuration, or with unavailable required runtime dependencies.

---

# Action

The operator runs `python -m src.main` with the invalid configuration
source selected by `--config` or `CONFIG_FILE_S3_PATH`.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Missing, malformed, or invalid runtime configuration | Startup fails before the bot becomes available and logs an error for the invalid configuration. |
| Unavailable required runtime dependency | Startup fails before the bot becomes available and logs an error for the unavailable dependency. |
| Omitted `--log-path` with otherwise valid configuration | Startup continues and warns that logging is console-only. |

---

# Outcome

Invalid startup conditions are reported before the bot becomes
available. A missing log path is treated as a warning when the remaining
runtime configuration is valid.

---

# Related Scenarios

- [Starts bot runtime](starts_bot_runtime.md)
- [Loads runtime configuration](../configuration/loads_runtime_configuration.md)
