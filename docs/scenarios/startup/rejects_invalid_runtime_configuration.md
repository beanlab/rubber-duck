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

# Outcome

Startup fails before the bot becomes available, and the application logs
an error for the invalid dependency or configuration.

If `--log-path` is omitted while the remaining runtime configuration is
valid, startup continues and the application warns that logging is
console-only.

---

# Related Scenarios

- [Starts bot runtime](starts_bot_runtime.md)
- [Loads runtime configuration](../configuration/loads_runtime_configuration.md)
