---
name: Config Assistance
description: |
  Instructions for how to provide developer assistance when working with the configs.
  If you are asked to help with anything involving the config, load this skill.
---

## Relevant File Locations

- `production-config.yaml`
- `local-config-example.yaml` (contains `$include` usage examples)
- `local-testing-configs/local-<name>-config.yaml`
- `src/utils/config_types.py`
- `src/utils/config_loader.py`
- `src/main.py`

## Config Model (Top-Level)

Use `src/utils/config_types.py` as the source of truth for expected sections:

- `sql`
- `containers`
- `tools`
- `cache`
- `ducks`
- `agents_as_tools`
- `servers`
- `admin_settings`
- `ai_completion_retry_protocol`
- `feedback_notifier_settings` (optional)
- `reporter_settings`
- `sender_email`

## Includes and Overrides

`$include` syntax:

- Include full file:
  - `$include: "production-config.yaml"`
- Include section with JSONPath:
  - `$include: "production-config.yaml@$.cache"`
- Multiple includes:
  - `$include_0`, `$include_1`, etc. (applied in sorted key order)

Override example:

```yaml
cache:
  $include: "production-config.yaml@$.cache"
  engine: gpt-5-mini
```

## Common Error Points

- Dict includes are deep-merged, then sibling keys override.
- If an include resolves to a non-dict (string/list/etc), it cannot have sibling keys.
- Multiple non-dict includes cannot be merged.
- Cyclic includes raise an error.
- Missing JSONPath match raises an error.
- Both local paths and `s3://` URIs are supported.




