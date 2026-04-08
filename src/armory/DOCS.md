## Purpose

`src/armory` owns tool registration, schema generation, and runtime tool execution wrappers.

## Operational Flow

- `Armory.scrub_tools(...)` discovers `@register_tool` methods and registers them.
- `add_tool(...)` wraps tools to accept `DuckContext`, tracks `complete_response` behavior, and stores strict function schemas.
- `generate_function_schema(...)` derives strict JSON schema from Python type hints.
- `PythonTools.run_code(...)` executes containerized Python, normalizes scientific notation in stdout/stderr, sends generated files/tables/stdout to Discord, and caches outputs.
- `send_table(...)` now renders numeric cells as plain decimal strings (rounded/trimmed) and disables markdown numeric parsing to preserve formatting.
- `DatasetTools.describe_dataset(...)` returns full dataset metadata by exact staged filename and reports valid filenames when no match exists.
- `TalkTool` provides conversation tools (`talk_to_user`, send/receive file/message, conclude).

## Dependencies

- Depends on `utils.python_exec_container` for execution sandbox behavior and dataset metadata lookup.
- Depends on cache implementations in `tool_cache.py` (`InMemoryToolCache`, `SqlToolCache`, `SemanticCacheKeyBuilder`).

## Failure Modes and Guardrails

- Tool parameters must be type-annotated for schema generation.
- Duplicate tool names overwrite earlier registrations.
- `DatasetTools.describe_dataset(...)` requires exact filename matches.
- `SqlToolCache` requires a valid SQLAlchemy bind at initialization.
