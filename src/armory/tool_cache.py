import hashlib
import json
from textwrap import dedent
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage
from ..utils.python_exec_container import FileResult


class CacheKey(BaseModel):
    dataset: list[str]
    analysis: list[str] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    plot_type: str | None = None
    special_requests: list[str] = Field(default_factory=list)


class CacheEntry(BaseModel):
    stdout: str | None = None
    tables: list[str] = Field(default_factory=list)
    files: dict[str, FileResult] = Field(default_factory=dict)


class InMemoryToolCache:
    def __init__(self, cache_store: dict[str, CacheEntry] | None = None):
        self._cache_store = cache_store if cache_store is not None else {}

    @staticmethod
    def _hash_key(key: CacheKey) -> str:
        canonical = json.dumps(
            key.model_dump(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def check_if_cached(self, cache_key: CacheKey) -> bool:
        key_hash = self._hash_key(cache_key)
        return key_hash in self._cache_store

    async def send_from_cache(self, cache_key: CacheKey, send_message: SendMessage, channel_id: int) -> dict[str, Any]:
        key_hash = self._hash_key(cache_key)
        entry = self._cache_store.get(key_hash)

        if entry is None:
            return {}

        for filename, file_data in entry.files.items():
            await send_message(
                channel_id,
                file={
                    "filename": filename,
                    "bytes": file_data["bytes"],
                }
            )

        for table_chunk in entry.tables:
            await send_message(channel_id, table_chunk)

        if entry.stdout:
            await send_message(channel_id, entry.stdout)

        output = {
            "stdout": entry.stdout or "",
            "stderr": "",
            "files": {
                filename: file_data["description"]
                for filename, file_data in entry.files.items()
            },
        }

        return output

    def _get_or_create(self, cache_key: CacheKey) -> CacheEntry:
        key_hash = self._hash_key(cache_key)
        if key_hash not in self._cache_store:
            self._cache_store[key_hash] = CacheEntry()
        return self._cache_store[key_hash]

    def cache_file(self, cache_key: CacheKey, filename: str, file: FileResult) -> None:
        duck_logger.debug(f"Caching file: {filename}")
        entry = self._get_or_create(cache_key)
        entry.files[filename] = {
            "bytes": file["bytes"],
            "description": file.get("description", ""),
        }

    def cache_table(self, cache_key: CacheKey, table_chunks: list[str]) -> None:
        if not table_chunks:
            return
        duck_logger.debug(f"Caching table: {table_chunks[0]}")
        entry = self._get_or_create(cache_key)
        entry.tables.extend(table_chunks)

    def cache_msg(self, cache_key: CacheKey, msg: str) -> None:
        duck_logger.debug(f"Caching message: {msg}")
        entry = self._get_or_create(cache_key)
        entry.stdout = msg


class SemanticCacheKeyBuilder:
    def __init__(
            self,
            client: OpenAI,
            prompt: str,
            model: str = "gpt-5-nano",
            reasoning_effort: str = "minimal"
    ):
        self._client = client
        self._prompt = prompt
        self._model = model
        self._reasoning_effort = reasoning_effort

    @staticmethod
    def _extract_text(response: Any) -> str:
        if getattr(response, "output_text", None):
            return response.output_text

        output = getattr(response, "output", [])
        for item in output:
            for content in getattr(item, "content", []):
                text = getattr(content, "text", None)
                if text:
                    return text

        raise ValueError("No text content returned when building semantic cache key")

    def build_cache_key(self, last_3_messages: str, code: str) -> CacheKey:
        user_prompt = dedent(
            f"""
            LAST 3 MESSAGES:
            {last_3_messages}

            PYTHON CODE:
            {code}

            Return a JSON object matching the CacheKey schema.
            """
        )

        try:
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {"role": "system", "content": self._prompt},
                    {"role": "user", "content": user_prompt},
                ],
                reasoning={"effort": self._reasoning_effort},
            )

            raw_json = self._extract_text(response)
            return CacheKey.model_validate(json.loads(raw_json))
        except Exception as exc:
            duck_logger.error(exc)
            raise
