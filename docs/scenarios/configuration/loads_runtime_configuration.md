# Loads Runtime Configuration

## Purpose

Select config source.

---

# Context

An operator starts the application with a local path, an S3 URI, or no
explicit `--config` argument. The required and optional top-level
configuration sections are defined in [Configuration
Scenarios](README.md).

---

# Action

The application begins startup configuration loading.

---

# Interaction

| Action | Outcome |
| --- | --- |
| The operator provides a local JSON or YAML path with `--config`. | The application reads runtime configuration from the local file. |
| The operator provides an `s3://` URI with `--config`. | The application reads runtime configuration from S3. |
| The operator omits `--config`. | The application attempts to read the configuration source from `CONFIG_FILE_S3_PATH`. |

---

# Outcome

The selected configuration source is loaded before runtime validation
and startup can continue.

---

# Related Scenarios

- [Starts bot runtime](../startup/starts_bot_runtime.md)
- [Rejects invalid runtime configuration](../startup/rejects_invalid_runtime_configuration.md)
- [Resolves included configuration](resolves_included_configuration.md)
