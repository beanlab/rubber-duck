import hashlib
import json
from datetime import datetime, timedelta, timezone
from textwrap import dedent
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage, ToolCache
from ..utils.python_exec_container import FileResult


class CacheKey(BaseModel):
    dataset: list[str]
    analysis: list[str] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class CacheEntry(BaseModel):
    stdout: str | None = None
    tables: list[dict[str, Any]] = Field(default_factory=list)
    files: dict[str, FileResult] = Field(default_factory=dict)
    created_at: datetime
    last_access: datetime
    hit_count: int
    expires_at: datetime


class InMemoryToolCache(ToolCache):
    def __init__(self, cache_store: dict[str, CacheEntry] | None = None):
        self._cache_store = cache_store if cache_store is not None else {}
        self._last_cleanup_at: datetime | None = None

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_key(key: CacheKey) -> str:
        canonical = json.dumps(
            key.model_dump(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def get_key_hash(self, cache_key: CacheKey) -> str:
        return self._hash_key(cache_key)

    def check_if_cached(self, key_hash: str) -> bool:
        result = key_hash in self._cache_store
        return result

    async def send_from_cache(self, key_hash: str, send_message: SendMessage, channel_id: int) -> dict[str, Any]:
        entry = self._cache_store.get(key_hash)

        if entry is None:
            duck_logger.error(f"Key {key_hash} not in cache")
            return {}

        now = self._utc_now()
        entry.hit_count += 1
        entry.last_access = now
        if entry.hit_count >= 10:
            entry.expires_at = now + timedelta(days=548)
        else:
            entry.expires_at = now + timedelta(days=entry.hit_count + 1)

        for filename, file_data in entry.files.items():
            await send_message(
                channel_id,
                file={
                    "filename": filename,
                    "bytes": file_data["bytes"],
                }
            )

        for table in entry.tables:
            for table_chunk in table["chunks"]:
                await send_message(channel_id, table_chunk)

        if entry.stdout:
            await send_message(channel_id, entry.stdout)

        files = {
            filename: file_data["description"]
            for filename, file_data in entry.files.items()
        }

        for table in entry.tables:
            files[table["filename"]] = table.get("description", "")

        output = {
            "stdout": entry.stdout or "",
            "stderr": "",
            "files": files,
        }

        return output

    def _get_or_create(self, key_hash: str) -> CacheEntry:
        if key_hash not in self._cache_store:
            now = self._utc_now()
            self._cache_store[key_hash] = CacheEntry(
                hit_count=0,
                created_at=now,
                last_access=now,
                expires_at=now + timedelta(days=1),
            )
        return self._cache_store[key_hash]

    def cleanup(self):
        now = self._utc_now()
        if self._last_cleanup_at is not None and (now - self._last_cleanup_at) < timedelta(days=1):
            return

        self._cache_store = {
            key_hash: entry
            for key_hash, entry in self._cache_store.items()
            if entry.expires_at >= now
        }
        self._last_cleanup_at = now

    def cache_file(self, key_hash: str, filename: str, file: FileResult):
        duck_logger.debug(f"Caching file: {filename}")
        entry = self._get_or_create(key_hash)
        entry.files[filename] = {
            "bytes": file["bytes"],
            "description": file.get("description", ""),
        }

    def cache_table(self, key_hash: str, filename: str, table_chunks: list[str], description: str = ""):
        if not table_chunks:
            return
        duck_logger.debug(f"Caching table: {filename}")
        entry = self._get_or_create(key_hash)
        entry.tables.append({
            "filename": filename,
            "description": description,
            "chunks": table_chunks,
        })

    def cache_msg(self, key_hash: str, msg: str):
        duck_logger.debug(f"Caching message: {msg}")
        entry = self._get_or_create(key_hash)
        entry.stdout = msg


class SemanticCacheKeyBuilder:
    def __init__(
            self,
            client: OpenAI,
            prompt: str,
            model: str = "gpt-5-mini",
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

    def build_cache_key(self, user_intent: str, code: str) -> CacheKey:
        user_prompt = dedent(
            f"""
            USER INTENT:
            {user_intent}

            PYTHON CODE:
            {code}
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
            data = json.loads(raw_json)
            # ensure it's always lowercase to increase hit chance
            data["dataset"] = [x.lower() for x in data.get("dataset", [])]
            data["analysis"] = [x.lower() for x in data.get("analysis", [])]
            data["parameters"] = {
                k.lower(): v.lower() if isinstance(v, str) else v
                for k, v in data.get("parameters", {}).items()
            }

            return CacheKey.model_validate(data)
        except Exception as exc:
            duck_logger.error(exc)
            raise
