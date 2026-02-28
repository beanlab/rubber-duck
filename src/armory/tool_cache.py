import hashlib
import json
import asyncio
import re
import os
from textwrap import dedent
from typing import Any, Callable, Awaitable, Optional
from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator

from ..utils.config_types import DuckContext
from ..utils.python_exec_container import PythonExecContainer
from ..utils.logger import duck_logger


class CanonicalCacheKey(BaseModel):
    dataset: Optional[str] = None
    columns: list[str] = []
    analysis: Optional[str] = None
    parameters: dict[str, Any] = {}
    plot_type: Optional[str] = None
    special_requests: list[str] = []

    @field_validator("*", mode="before")
    def normalize_strings(cls, v):
        if isinstance(v, str):
            # lowercase, replace spaces with underscores, strip punctuation
            v = v.lower()
            v = re.sub(r"[^\w\s]", "", v)
            v = re.sub(r"\s+", "_", v.strip())
        elif isinstance(v, list):
            # normalize all strings in lists
            v = [
                re.sub(r"[^\w\s]", "", str(x).lower()).replace(" ", "_").strip() if isinstance(x, str) else x
                for x in v
            ]
            v.sort()  # sort lists for consistent ordering
        elif isinstance(v, dict):
            # normalize keys
            new_dict = {}
            for k, val in v.items():
                nk = re.sub(r"[^\w\s]", "", str(k).lower()).replace(" ", "_").strip()
                if isinstance(val, str):
                    val = re.sub(r"[^\w\s]", "", val.lower()).replace(" ", "_").strip()
                new_dict[nk] = val
            v = new_dict
        return v


class ToolCache:
    """Simple in-memory async-safe cache"""

    def __init__(self):
        self._store: dict[str, Any] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _hash_key(self, key_dict: dict) -> str:
        canonical = json.dumps(key_dict, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _get_lock(self, hashed_key: str) -> asyncio.Lock:
        if hashed_key not in self._locks:
            self._locks[hashed_key] = asyncio.Lock()
        return self._locks[hashed_key]

    async def get(self, key_dict: dict):
        hashed = self._hash_key(key_dict)
        return self._store.get(hashed)

    async def set(self, key_dict: dict, value: Any):
        hashed = self._hash_key(key_dict)
        self._store[hashed] = value

    async def run_with_cache(self, key_dict: dict, executor: Callable[[], Awaitable[Any]]):
        """Prevent duplicate concurrent executions for the same key."""
        hashed = self._hash_key(key_dict)
        lock = self._get_lock(hashed)

        async with lock:
            if hashed in self._store:
                return self._store[hashed]

            result = await executor()
            self._store[hashed] = result
            return result


async def make_semantic_cache_key(ctx: DuckContext, tool_name: str, code: str, last_3_messages: str) -> CanonicalCacheKey:
    """Generate a canonical JSON cache key from the user prompt using GPT"""
    example_analyses = ["head", "mean", "z_test", "anova", "density_plot", "summary_stats"]

    schema_json = json.dumps(CanonicalCacheKey.model_json_schema(), indent=2)

    system_prompt = dedent(f"""
        You are a tool that maps any natural language user request to a canonical JSON cache key.
        Use this schema:
        
        {schema_json}
        
        - Normalize strings to lowercase with underscores.
        - Include inferred fields if dataset/columns/analysis are not explicit.
        - Always output valid JSON.
        - Only include fields in the schema; do not add extra fields.
        - For analysis, use one of {example_analyses} if appropriate, otherwise choose the most semantically meaningful.
        """
    )

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("SEMANTIC_CACHE_MODEL", "gpt-4.1-mini")
    duck_logger.debug(f"[CACHE KEY] Using semantic model '{model}' for tool '{tool_name}'")
    user_prompt = dedent(f"""
        Tool name: {tool_name}
        Initial user message: {ctx.content}
        Last 3 messages (JSON string): {last_3_messages}
        Python code to run:
        ```python
        {code}
        ```

        Return only one JSON object matching the schema.
    """)

    try:
        response = await client.responses.create(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            max_output_tokens=220
        )

        raw_text = (response.output_text or "").strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            if raw_text.startswith("json"):
                raw_text = raw_text[4:].strip()

        if "{" in raw_text and "}" in raw_text:
            raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]

        key_model = CanonicalCacheKey.model_validate_json(raw_text)
    except Exception:
        # fallback to empty/default key
        key_model = CanonicalCacheKey(
            tool_name=tool_name,
            code=code,
            last_3_messages=last_3_messages
        )

    return key_model


def wrap_tool_with_cache(tool_func: Callable, cache: ToolCache, tool_name: str, container: PythonExecContainer):
    async def wrapped(ctx: DuckContext, code: str, last_3_messages: str):
        key = await make_semantic_cache_key(ctx, tool_name, code, last_3_messages)
        key_payload = key.model_dump()
        duck_logger.debug(f"[CACHE KEY] Generated key for {tool_name}: {json.dumps(key_payload, sort_keys=True)}")

        async def execute():
            duck_logger.debug(f"[CACHE MISS] Executing {tool_name} for thread {ctx.thread_id}")
            result = await tool_func(ctx, code, last_3_messages)
            return {"return_value": result, "messages": result.get("messages_sent", [])}

        cached_result = await cache.run_with_cache(key_payload, execute)

        if cached_result["messages"]:
            duck_logger.debug(f"[CACHE HIT] Replaying {len(cached_result['messages'])} messages for {tool_name}")

        return cached_result["return_value"]

    return wrapped
