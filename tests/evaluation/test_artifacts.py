import json

import pytest

from src.evaluation.artifacts import (
    ArtifactCollisionError,
    ArtifactExistsError,
    ArtifactIntegrityError,
    ArtifactStore,
    ArtifactStoreError,
)
from src.evaluation.schemas import EvaluationDeclaration


def test_artifact_round_trip_and_immutable_write(tmp_path, smoke_fixture):
    store = ArtifactStore(tmp_path / "artifacts")
    declaration = smoke_fixture.declaration
    store.put(
        "declarations",
        declaration.run_id,
        declaration,
        producer="test-suite",
    )

    restored = store.get(
        "declarations", declaration.run_id, EvaluationDeclaration
    )
    assert restored == declaration
    assert store.list_ids("declarations") == (declaration.run_id,)

    with pytest.raises(ArtifactExistsError):
        store.put(
            "declarations",
            declaration.run_id,
            declaration,
            producer="test-suite",
        )


@pytest.mark.parametrize(
    "artifact_type,artifact_id",
    [
        ("../outside", "safe"),
        ("/absolute", "safe"),
        ("trials", "../../outside"),
        ("trials", "/absolute"),
        ("trials", "tríal"),
    ],
)
def test_artifact_store_rejects_unsafe_paths(
    tmp_path, artifact_type, artifact_id
):
    store = ArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ArtifactStoreError):
        store.put(
            artifact_type,
            artifact_id,
            {"safe": True},
            producer="test-suite",
        )


def test_artifact_store_rejects_symlink_escape(tmp_path):
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "trials").symlink_to(outside, target_is_directory=True)
    store = ArtifactStore(root)

    with pytest.raises(ArtifactStoreError, match="symlink"):
        store.put("trials", "trial-1", {"safe": True}, producer="test-suite")


def test_foreign_lock_is_not_removed(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts")
    directory = store.root / "trials"
    directory.mkdir()
    lock = directory / "trial-1.lock"
    lock.write_text("held elsewhere", encoding="utf-8")

    with pytest.raises(ArtifactCollisionError):
        store.put("trials", "trial-1", {"safe": True}, producer="test-suite")

    assert lock.read_text(encoding="utf-8") == "held elsewhere"


def test_payload_tampering_is_detected(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts")
    store.put("trials", "trial-1", {"answer": 1}, producer="test-suite")
    path = store.root / "trials" / "trial-1.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["payload"]["answer"] = 2
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ArtifactIntegrityError):
        store.get_envelope("trials", "trial-1")
