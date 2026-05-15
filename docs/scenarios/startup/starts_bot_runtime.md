# Starts Bot Runtime

## Purpose

Start the Discord bot.

---

# Context

An operator has a valid runtime configuration available as a local JSON
or YAML file, an `s3://` URI, or the `CONFIG_FILE_S3_PATH` environment
variable. The configuration includes the required runtime sections and
valid Discord, SQL, duck, tool, and reporting settings.

---

# Action

The operator runs `python -m src.main` with optional `--config`,
`--debug`, and `--log-path` arguments.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Valid runtime configuration | Loads and resolves configuration, connects required runtime dependencies, initializes configured ducks and tools, and starts the Discord bot loop. |
| Successful startup | Sends `Duck online` to the configured admin channel. |
| `--debug` | Uses debug verbosity for runtime logging. |
| `--log-path` | Writes runtime logs to that path. |

---

# Outcome

Successful startup makes the Discord bot available and reports readiness
in the configured admin channel.

---

# Related Scenarios

- [Rejects invalid runtime configuration](rejects_invalid_runtime_configuration.md)
- [Loads runtime configuration](../configuration/loads_runtime_configuration.md)
- [Resolves included configuration](../configuration/resolves_included_configuration.md)
