## Relevant File Locations

- `src/armory/armory.py`
- `src/armory/tools.py`
- `src/armory/python_tools.py`
- `src/armory/talk_tool.py`
- `src/armory/tool_cache.py`
- `src/armory/cache.py`

## Core Responsibilities

- `Armory` (`armory.py`) stores tool callables and JSON schemas, wraps call sites with `DuckContext`, and exposes lookup
  helpers.
- `register_tool` / `sends_image` decorators (`tools.py`) mark methods for tool registration and direct image handling.
- `generate_function_schema` (`tools.py`) builds strict function schemas from Python type hints and docstrings.
- `PythonTools.run_code` executes user code and coordinates semantic caching through `ToolCache` and `CacheKeyBuilder`.
- `TalkTool` methods provide user-facing communication/file-send tools for agents.

## Tool Cache Implementations

- `InMemoryToolCache`: process-local cache (good for tests/local development).
- `SqlToolCache`: persistent cache table (`tool_cache`) via SQLAlchemy session.
- `SemanticCacheKeyBuilder`: derives normalized cache keys from user intent and code using model text extraction.

## Common Error Points

- Missing/weak type hints on tool functions produce incomplete schemas.
- Tool names collide when multiple registered methods resolve to the same function name.
- Cached outputs can become stale if cache key inputs do not include relevant intent/code context.
- SQL cache requires a valid SQLAlchemy bind; initialization fails without one.
- `send_from_cache` expects cache entries to match channel/file output assumptions.