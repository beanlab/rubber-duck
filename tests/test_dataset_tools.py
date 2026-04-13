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
from src.utils.config_types import DuckContext
from src.utils.protocols import ConcludesResponse


class _FakeContainer:
    def __init__(self, inventory):
        self._inventory = inventory

    def get_dataset_inventory(self):
        return self._inventory


def _ctx(thread_id=999) -> DuckContext:
    return DuckContext(
        guild_id=1,
        parent_channel_id=2,
        author_id=3,
        author_mention="@user",
        content="list datasets",
        message_id=4,
        thread_id=thread_id,
        timeout=60,
    )


def test_send_datasets_to_user_sorts_dedupes_and_falls_back_to_filename():
    sent_messages = []

    async def _send_message(_channel_id, message=None, file=None, view=None):
        if message is not None:
            sent_messages.append(message)
        return 1

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
    tools = DatasetTools(containers, _send_message)

    result = asyncio.run(tools.send_datasets_to_user(_ctx()))

    assert isinstance(result, ConcludesResponse)
    assert result.result == "Sent 4 dataset names."
    assert len(sent_messages) == 1
    assert sent_messages[0] == "\n".join(
        [
            "Available datasets:",
            "- Alpha",
            "- beta",
            "- fallback.csv",
            "- zeta",
        ]
    )


def test_send_datasets_to_user_sends_full_large_list():
    sent_messages = []

    async def _send_message(_channel_id, message=None, file=None, view=None):
        if message is not None:
            sent_messages.append(message)
        return 1

    inventory = [
        {"dataset_name": f"Dataset {i:03d}", "filename": f"dataset_{i:03d}.csv", "path": "/d/x.csv"}
        for i in range(220)
    ]
    tools = DatasetTools([_FakeContainer(inventory)], _send_message)

    result = asyncio.run(tools.send_datasets_to_user(_ctx()))

    assert isinstance(result, ConcludesResponse)
    assert len(sent_messages) == 1
    rendered = sent_messages[0]
    assert "- Dataset 000" in rendered
    assert "- Dataset 219" in rendered


def test_send_datasets_to_user_reports_empty_inventory():
    sent_messages = []

    async def _send_message(_channel_id, message=None, file=None, view=None):
        if message is not None:
            sent_messages.append(message)
        return 1

    tools = DatasetTools([_FakeContainer([])], _send_message)

    result = asyncio.run(tools.send_datasets_to_user(_ctx()))

    assert isinstance(result, ConcludesResponse)
    assert result.result == "No datasets are currently available."
    assert sent_messages == ["No datasets are currently available."]
