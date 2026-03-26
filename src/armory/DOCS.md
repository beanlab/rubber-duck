## Purpose

`src/armory` owns tool registration, schema generation, and runtime tool execution wrappers.

## Operational Flow

- `Armory.scrub_tools(...)` discovers `@register_tool` methods and registers them.
- `add_tool(...)` wraps tools to accept `DuckContext`, tracks `complete_response` behavior, and stores strict function schemas.
- `generate_function_schema(...)` derives strict JSON schema from Python type hints.
- `PythonTools.run_code(...)` executes containerized Python, sends generated files/tables/stdout to Discord, and caches outputs.
- `TalkTool` provides conversation tools (`talk_to_user`, send/receive file/message, conclude).

## Dependencies

- Depends on `utils.python_exec_container` for execution sandbox behavior.
- Depends on cache implementations in `tool_cache.py` (`InMemoryToolCache`, `SqlToolCache`, `SemanticCacheKeyBuilder`).

## Failure Modes and Guardrails

- Tool parameters must be type-annotated for schema generation.
- Duplicate tool names overwrite earlier registrations.
- `SqlToolCache` requires a valid SQLAlchemy bind at initialization.
