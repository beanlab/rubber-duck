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
| The selected runtime configuration is missing, malformed, or invalid. | Startup fails before the bot becomes available, and the application logs an error for the invalid configuration. |
| A required runtime dependency is unavailable. | Startup fails before the bot becomes available, and the application logs an error for the unavailable dependency. |
| `--log-path` is omitted while the remaining runtime configuration is valid. | Startup continues, and the application warns that logging is console-only. |

---

# Outcome

Invalid startup conditions are reported before the bot becomes
available. A missing log path is treated as a warning when the remaining
runtime configuration is valid.

---

# Related Scenarios

- [Starts bot runtime](starts_bot_runtime.md)
- [Loads runtime configuration](../configuration/loads_runtime_configuration.md)
