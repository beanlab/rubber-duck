import asyncio
import sys
import types


boto3_stub = types.ModuleType("boto3")
boto3_stub.client = lambda *_args, **_kwargs: types.SimpleNamespace()
sys.modules.setdefault("boto3", boto3_stub)

botocore_stub = types.ModuleType("botocore")
botocore_exceptions_stub = types.ModuleType("botocore.exceptions")


class _ClientError(Exception):
    pass


botocore_exceptions_stub.ClientError = _ClientError
botocore_stub.exceptions = botocore_exceptions_stub
sys.modules.setdefault("botocore", botocore_stub)
sys.modules.setdefault("botocore.exceptions", botocore_exceptions_stub)

from src.armory.python_tools import DatasetTools
from src.utils.python_exec_container import PythonExecContainer


class _FakeContainer(PythonExecContainer):
    def __init__(self, inventory: list[dict[str, str]]) -> None:
        self._inventory = inventory

    def get_dataset_inventory(self) -> list[dict[str, str]]:
        return self._inventory


class _TextOutput:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def capture_text(self, message: str) -> None:
        self.messages.append(message)


def test_send_datasets_to_user_sorts_dedupes_and_falls_back_to_filename() -> None:
    containers = [
        _FakeContainer(
            [
                {"dataset_name": "zeta", "filename": "zeta.csv", "path": "/d/zeta.csv"},
                {"dataset_name": "Alpha", "filename": "alpha.csv", "path": "/d/alpha.csv"},
                {"filename": "fallback.csv", "path": "/d/fallback.csv"},
            ]
        ),
        _FakeContainer(
            [
                {"dataset_name": "Alpha", "filename": "alpha-2.csv", "path": "/d/alpha-2.csv"},
                {"dataset_name": "beta", "filename": "beta.csv", "path": "/d/beta.csv"},
            ]
        ),
    ]
    tools = DatasetTools(containers)
    output = _TextOutput()

    result = asyncio.run(tools.send_datasets_to_user(output))

    assert result == "Prepared 4 dataset names for delivery."
    assert output.messages == ["\n".join(
        [
            "Available datasets:",
            "- Alpha",
            "- beta",
            "- fallback.csv",
            "- zeta",
        ]
    )]


def test_send_datasets_to_user_sends_full_large_list() -> None:
    inventory = [
        {
            "dataset_name": f"Dataset {i:03d}",
            "filename": f"dataset_{i:03d}.csv",
            "path": "/d/x.csv",
        }
        for i in range(220)
    ]
    tools = DatasetTools([_FakeContainer(inventory)])
    output = _TextOutput()

    result = asyncio.run(tools.send_datasets_to_user(output))

    assert result == "Prepared 220 dataset names for delivery."
    assert len(output.messages) == 1
    rendered = output.messages[0]
    assert "- Dataset 000" in rendered
    assert "- Dataset 219" in rendered


def test_send_datasets_to_user_reports_empty_inventory() -> None:
    tools = DatasetTools([_FakeContainer([])])
    output = _TextOutput()

    result = asyncio.run(tools.send_datasets_to_user(output))

    assert result == "Prepared 0 dataset names for delivery."
    assert output.messages == ["No datasets are currently available."]
