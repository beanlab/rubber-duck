# Configuration Scenarios

Configuration scenarios describe the external runtime configuration
contract used during startup.

The required top-level runtime sections are `sql`, `containers`,
`tools`, `ducks`, `servers`, `admin_settings`,
`ai_completion_retry_protocol`, `reporter_settings`, and `sender_email`.

Optional top-level sections include `feedback_notifier_settings`,
`cache_cleanup_settings`, and `agents_as_tools`.

Runtime configuration may be selected from a local path, an `s3://` URI,
or `CONFIG_FILE_S3_PATH` when no explicit `--config` argument is given.

## Scenarios

- [Loads runtime configuration](loads_runtime_configuration.md)
- [Resolves included configuration](resolves_included_configuration.md)
