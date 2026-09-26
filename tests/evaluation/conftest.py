from pathlib import Path

import pytest

from src.evaluation.schemas import OfflineFixture


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "evaluation_assets" / "examples"


def load_example(name: str) -> OfflineFixture:
    return OfflineFixture.model_validate_json(
        (EXAMPLES / name).read_text(encoding="utf-8")
    )


@pytest.fixture
def smoke_fixture() -> OfflineFixture:
    return load_example("offline-smoke.json")


@pytest.fixture
def no_effect_fixture() -> OfflineFixture:
    return load_example("offline-no-effect.json")
