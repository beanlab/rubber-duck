# Loads Runtime Configuration

## Purpose

Select config source.

---

# Context

An operator starts the application with a local path, an S3 URI, or no
explicit `--config` argument.

---

# Action

The application begins startup configuration loading.

---

# Outcome

The application accepts JSON or YAML configuration from a local path or
an `s3://` URI. If `--config` is omitted, the application attempts to
read the configuration source from `CONFIG_FILE_S3_PATH`.

The external configuration contract includes the required top-level
runtime sections `sql`, `containers`, `tools`, `ducks`, `servers`,
`admin_settings`, `ai_completion_retry_protocol`, `reporter_settings`,
and `sender_email`. Optional top-level sections include
`feedback_notifier_settings`, `cache_cleanup_settings`, and
`agents_as_tools`.

---

# Related Scenarios

- [Starts bot runtime](../startup/starts_bot_runtime.md)
- [Rejects invalid runtime configuration](../startup/rejects_invalid_runtime_configuration.md)
- [Resolves included configuration](resolves_included_configuration.md)
