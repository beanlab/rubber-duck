import json
import hashlib
from pathlib import Path
from textwrap import dedent
from typing import Optional, Any
from pydantic import BaseModel
from openai import OpenAI

from ..utils.logger import duck_logger
from ..utils.python_exec_container import FileResult


class CacheKey(BaseModel):
    dataset: list[str]
    analysis: Optional[list[str]] = None
    parameters: dict[str, Any] = {}
    plot_type: Optional[str] = None
    special_requests: Optional[list[str]] = []


class CacheEntry(BaseModel):
    stdout: Optional[str] = None
    tables: Optional[list[str]] = []
    files: Optional[dict[str, FileResult]] = {}


# ----------------------------
# In-memory store
# ----------------------------

_cache_store: dict[str, CacheEntry] = {}


def _hash_key(key: CacheKey) -> str:
    canonical = json.dumps(
        key.model_dump(),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ----------------------------
# Public Cache API
# ----------------------------

def check_if_cached(cache_key: CacheKey) -> bool:
    key_hash = _hash_key(cache_key)
    return key_hash in _cache_store


def send_from_cache(cache_key: CacheKey) -> dict:
    key_hash = _hash_key(cache_key)
    entry = _cache_store.get(key_hash)

    if entry is None:
        return {}

    stdout = entry.stdout or ""
    stderr = ""

    files = {
        filename: file_data["description"]
        for filename, file_data in entry.files.items()
    }

    output = {
        "stdout": stdout,
        "stderr": stderr,
        "files": files,
    }

    return output


def cache_file(cache_key: CacheKey, filename: str, file: FileResult) -> None:
    duck_logger.debug(f"Caching file: {filename}")
    key_hash = _hash_key(cache_key)

    if key_hash not in _cache_store:
        _cache_store[key_hash] = CacheEntry()

    _cache_store[key_hash].files[filename] = {
        "bytes": file["bytes"],
        "description": file.get("description", ""),
    }


def cache_table(cache_key: CacheKey, table_chunks: list[str]) -> None:
    duck_logger.debug(f"Caching table: {table_chunks[0]}")
    key_hash = _hash_key(cache_key)

    if key_hash not in _cache_store:
        _cache_store[key_hash] = CacheEntry()

    _cache_store[key_hash].tables.extend(table_chunks)


def cache_msg(cache_key: CacheKey, msg: str) -> None:
    duck_logger.debug(f"Caching message: {msg}")
    key_hash = _hash_key(cache_key)

    if key_hash not in _cache_store:
        _cache_store[key_hash] = CacheEntry()

    _cache_store[key_hash].stdout = msg


# ----------------------------
# Semantic key creation
# ----------------------------

STATS_CACHE_PROMPT = Path("prompts/production-prompts/stats-cache.md").read_text()
_client = OpenAI()


def build_cache_key(last_3_messages: str, code: str) -> CacheKey:
    system_prompt = STATS_CACHE_PROMPT

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
        response = _client.responses.create(
            model="gpt-5-nano",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            reasoning={"effort": "minimal"},
        )

        raw_json = response.output[1].content[0].text
        data: CacheKey = json.loads(raw_json)

        return CacheKey.model_validate(data)

    except Exception as e:
        duck_logger.error(e)
        raise