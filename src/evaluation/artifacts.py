"""A small, content-verified filesystem artifact store."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .schemas import (
    ArtifactEnvelope,
    Identifier,
    Sensitivity,
    canonical_json,
    digest_json,
)


class ArtifactStoreError(RuntimeError):
    pass


class ArtifactExistsError(ArtifactStoreError):
    pass


class ArtifactCollisionError(ArtifactStoreError):
    pass


class ArtifactIntegrityError(ArtifactStoreError):
    pass


ModelT = TypeVar("ModelT", bound=BaseModel)


class ArtifactStore:
    """Persist immutable JSON envelopes beneath one explicit root."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._resolved_root = self.root.resolve()
        if not self._resolved_root.is_dir():
            raise ArtifactStoreError("artifact root must be a directory")

    @staticmethod
    def _validate_identifier(value: str, field_name: str) -> str:
        try:
            # Use the exact schema constraint shared by stored envelopes.
            from pydantic import TypeAdapter

            return TypeAdapter(Identifier).validate_python(value)
        except ValueError as error:
            raise ArtifactStoreError(f"invalid {field_name}: {value!r}") from error

    def _safe_path(self, artifact_type: str, artifact_id: str) -> Path:
        artifact_type = self._validate_identifier(artifact_type, "artifact type")
        artifact_id = self._validate_identifier(artifact_id, "artifact ID")
        directory = self.root / artifact_type
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            raise ArtifactStoreError("artifact type directory cannot be a symlink")
        try:
            directory.resolve().relative_to(self._resolved_root)
        except ValueError as error:
            raise ArtifactStoreError("artifact path escapes the store root") from error
        target = directory / f"{artifact_id}.json"
        if target.is_symlink():
            raise ArtifactStoreError("artifact target cannot be a symlink")
        return target

    def put(
        self,
        artifact_type: str,
        artifact_id: str,
        payload: BaseModel | dict[str, Any],
        *,
        producer: str,
        sensitivity: Sensitivity = Sensitivity.PUBLIC,
        parent_artifact_ids: tuple[str, ...] = (),
    ) -> ArtifactEnvelope:
        target = self._safe_path(artifact_type, artifact_id)
        producer = self._validate_identifier(producer, "producer")
        payload_dict = (
            payload.model_dump(mode="json", exclude_none=False)
            if isinstance(payload, BaseModel)
            else payload
        )
        envelope = ArtifactEnvelope(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            producer=producer,
            sensitivity=sensitivity,
            payload_digest=digest_json(payload_dict),
            payload=payload_dict,
            parent_artifact_ids=parent_artifact_ids,
        )

        lock_path = target.with_suffix(".lock")
        lock_fd: int | None = None
        owns_lock = False
        temp_path: Path | None = None
        try:
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                owns_lock = True
            except FileExistsError as error:
                raise ArtifactCollisionError(
                    f"another writer holds the artifact lock: {artifact_type}/{artifact_id}"
                ) from error

            if target.exists() or target.is_symlink():
                raise ArtifactExistsError(
                    f"artifact already exists: {artifact_type}/{artifact_id}"
                )

            serialized = canonical_json(envelope) + "\n"
            with tempfile.NamedTemporaryFile(
                mode="x",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{artifact_id}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(serialized)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, target)
            temp_path = None
            return envelope
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
            if owns_lock and lock_path.exists():
                lock_path.unlink()
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    def get_envelope(self, artifact_type: str, artifact_id: str) -> ArtifactEnvelope:
        target = self._safe_path(artifact_type, artifact_id)
        if not target.exists():
            raise FileNotFoundError(target)
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            envelope = ArtifactEnvelope.model_validate(raw)
        except (json.JSONDecodeError, ValueError) as error:
            raise ArtifactIntegrityError(
                f"invalid artifact: {artifact_type}/{artifact_id}"
            ) from error
        if envelope.artifact_type != artifact_type or envelope.artifact_id != artifact_id:
            raise ArtifactIntegrityError("artifact path and envelope identity differ")
        return envelope

    def get(self, artifact_type: str, artifact_id: str, model: type[ModelT]) -> ModelT:
        return model.model_validate(self.get_envelope(artifact_type, artifact_id).payload)

    def list_ids(self, artifact_type: str) -> tuple[str, ...]:
        artifact_type = self._validate_identifier(artifact_type, "artifact type")
        directory = self._safe_path(artifact_type, "probe").parent
        return tuple(
            path.stem
            for path in sorted(directory.glob("*.json"))
            if not path.is_symlink()
        )
