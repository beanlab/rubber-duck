import json
import base64
from datetime import datetime, timedelta, timezone
from textwrap import dedent
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, JSON, Text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

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


ToolCacheRecordBase = declarative_base()


class ToolCacheRecord(ToolCacheRecordBase):
    __tablename__ = "tool_cache"

    key = Column("key_hash", Text, primary_key=True)
    stdout = Column(Text, nullable=True)
    tables = Column(JSON, nullable=False, default=list)
    files = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)
    last_access = Column(DateTime(timezone=True), nullable=False)
    hit_count = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)


def _canonical_cache_key(cache_key: CacheKey) -> str:
    return json.dumps(
        cache_key.model_dump(),
        sort_keys=True,
        separators=(",", ":"),
    )


def _format_cache_report(records: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for key, record in records:
        tables = list(getattr(record, "tables", None) or [])
        files = dict(getattr(record, "files", None) or {})
        rows.append({
            "key_hash": key,
            "hits": getattr(record, "hit_count"),
            "txt": bool(getattr(record, "stdout", None)),
            "tabls": len(tables),
            "files": len(files),
            "last_hit": getattr(record, "last_access").strftime("%m/%d/%y"),
            "created": getattr(record, "created_at").strftime("%m/%d/%y"),
            "expires": getattr(record, "expires_at").strftime("%m/%d/%y"),
        })

    return rows


class InMemoryToolCache(ToolCache):
    def __init__(self, cache_store: dict[str, CacheEntry] | None = None):
        self._cache_store = cache_store if cache_store is not None else {}
        self._last_cleanup_at: datetime | None = None

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def get_key(self, cache_key: CacheKey) -> str:
        return _canonical_cache_key(cache_key)

    def check_if_cached(self, key: str) -> bool:
        result = key in self._cache_store
        return result

    async def send_from_cache(self, key: str, send_message: SendMessage, channel_id: int) -> dict[str, Any]:
        entry = self._cache_store.get(key)

        if entry is None:
            duck_logger.error(f"Key {key} not in cache")
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

    def _get_or_create(self, key: str) -> CacheEntry:
        if key not in self._cache_store:
            now = self._utc_now()
            self._cache_store[key] = CacheEntry(
                hit_count=0,
                created_at=now,
                last_access=now,
                expires_at=now + timedelta(days=1),
            )
        return self._cache_store[key]

    def cleanup(self):
        now = self._utc_now()
        if self._last_cleanup_at is not None and (now - self._last_cleanup_at) < timedelta(days=1):
            return

        self._cache_store = {
            key: entry
            for key, entry in self._cache_store.items()
            if entry.expires_at >= now
        }
        self._last_cleanup_at = now

    def cache_file(self, key: str, filename: str, file: FileResult):
        duck_logger.debug(f"Caching file: {filename}")
        entry = self._get_or_create(key)
        entry.files[filename] = {
            "bytes": file["bytes"],
            "description": file.get("description", ""),
        }

    def cache_table(self, key: str, filename: str, table_chunks: list[str], description: str = ""):
        if not table_chunks:
            return
        duck_logger.debug(f"Caching table: {filename}")
        entry = self._get_or_create(key)
        entry.tables.append({
            "filename": filename,
            "description": description,
            "chunks": table_chunks,
        })

    def cache_msg(self, key: str, msg: str):
        duck_logger.debug(f"Caching message: {msg}")
        entry = self._get_or_create(key)
        entry.stdout = msg

    def list_entries(self) -> list[dict[str, Any]]:
        return _format_cache_report(list(self._cache_store.items()))


class SqlToolCache(ToolCache):
    def __init__(self, session: Session):
        bind = session.get_bind()
        if bind is None:
            raise ValueError("Cannot initialize SqlToolCache without a SQLAlchemy bind")
        self._session_factory = sessionmaker(bind=bind)
        ToolCacheRecordBase.metadata.create_all(bind)
        self._last_cleanup_at: datetime | None = None

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _encode_file(file: FileResult) -> dict[str, str]:
        return {
            "bytes_b64": base64.b64encode(file["bytes"]).decode("ascii"),
            "description": file.get("description", ""),
        }

    @staticmethod
    def _decode_file(file_data: dict[str, str]) -> FileResult:
        return {
            "bytes": base64.b64decode(file_data["bytes_b64"]),
            "description": file_data.get("description", ""),
        }

    def get_key(self, cache_key: CacheKey) -> str:
        return _canonical_cache_key(cache_key)

    def _get_or_create(self, session: Session, key: str) -> ToolCacheRecord:
        record = session.get(ToolCacheRecord, key)
        if record is None:
            now = self._utc_now()
            record = ToolCacheRecord(
                key=key,
                stdout=None,
                tables=[],
                files={},
                hit_count=0,
                created_at=now,
                last_access=now,
                expires_at=now + timedelta(days=1),
            )
            session.add(record)
            session.flush()
        return record

    def check_if_cached(self, key: str) -> bool:
        with self._session_factory() as session:
            return session.get(ToolCacheRecord, key) is not None

    async def send_from_cache(self, key: str, send_message: SendMessage, channel_id: int) -> dict[str, Any]:
        with self._session_factory() as session:
            record = session.get(ToolCacheRecord, key)
            if record is None:
                duck_logger.error(f"Key {key} not in cache")
                return {}

            now = self._utc_now()
            record.hit_count += 1
            record.last_access = now
            if record.hit_count >= 10:
                record.expires_at = now + timedelta(days=548)
            else:
                record.expires_at = now + timedelta(days=record.hit_count + 1)

            files = {
                filename: self._decode_file(file_data)
                for filename, file_data in (record.files or {}).items()
            }
            tables = list(record.tables or [])
            stdout = record.stdout

            session.commit()

        for filename, file_data in files.items():
            await send_message(
                channel_id,
                file={
                    "filename": filename,
                    "bytes": file_data["bytes"],
                }
            )

        for table in tables:
            for table_chunk in table["chunks"]:
                await send_message(channel_id, table_chunk)

        if stdout:
            await send_message(channel_id, stdout)

        output_files = {
            filename: file_data["description"]
            for filename, file_data in files.items()
        }
        for table in tables:
            output_files[table["filename"]] = table.get("description", "")

        return {
            "stdout": stdout or "",
            "stderr": "",
            "files": output_files,
        }

    def cache_file(self, key: str, filename: str, file: FileResult):
        duck_logger.debug(f"Caching file: {filename}")
        with self._session_factory() as session:
            record = self._get_or_create(session, key)
            files = dict(record.files or {})
            files[filename] = self._encode_file(file)
            record.files = files
            session.commit()

    def cache_table(self, key: str, filename: str, table_chunks: list[str], description: str = ""):
        if not table_chunks:
            return
        duck_logger.debug(f"Caching table: {filename}")
        with self._session_factory() as session:
            record = self._get_or_create(session, key)
            tables = list(record.tables or [])
            tables.append({
                "filename": filename,
                "description": description,
                "chunks": table_chunks,
            })
            record.tables = tables
            session.commit()

    def cache_msg(self, key: str, msg: str):
        duck_logger.debug(f"Caching message: {msg}")
        with self._session_factory() as session:
            record = self._get_or_create(session, key)
            record.stdout = msg
            session.commit()

    def cleanup(self):
        now = self._utc_now()
        if self._last_cleanup_at is not None and (now - self._last_cleanup_at) < timedelta(days=1):
            return

        with self._session_factory() as session:
            expired_records = (
                session.query(ToolCacheRecord)
                .filter(ToolCacheRecord.expires_at < now)
                .all()
            )
            for record in expired_records:
                session.delete(record)
            session.commit()

        self._last_cleanup_at = now

    def list_entries(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            records = session.query(ToolCacheRecord).all()

        return _format_cache_report([(record.key, record) for record in records])


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
