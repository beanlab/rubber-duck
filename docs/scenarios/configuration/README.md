# Configuration Scenarios

Configuration scenarios describe the external runtime configuration
contract used during startup.

Runtime configuration may be selected from a local path, an `s3://` URI,
or `CONFIG_FILE_S3_PATH` when no explicit `--config` argument is given.

## Scenarios

- [Loads runtime configuration](loads_runtime_configuration.md)
- [Resolves included configuration](resolves_included_configuration.md)
