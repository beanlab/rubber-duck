"""Controlled dependencies for isolated Stats Duck response and delivery tests."""

import ast
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncIterator

from openai.types.responses import EasyInputMessageParam

from src.duck_protocols import DuckContext, MessageHandler
from src.utils.config_types import HistoryType
from src.utils.protocols import Message
from src.utils.python_exec_container import ExecutionResult, FileResult, PythonExecContainer


class FakeSandbox(PythonExecContainer):
    def __init__(
            self,
            datasets: list[dict],
            execution: str | None,
    ) -> None:
        self.datasets = datasets
        self.execution = execution
        self.generated_code: list[str] = []

    def get_dataset_inventory(self) -> list[dict[str, str]]:
        return [
            {"filename": item["filename"], "dataset_name": item["dataset_name"], "path": item["path"]}
            for item in self.datasets
        ]

    def describe_dataset(self, dataset_name: str) -> str | None:
        return next(
            (
                item["description"]
                for item in self.datasets
                if item["filename"] == dataset_name
            ),
            None,
        )

    async def run_code(self, code: str) -> ExecutionResult:
        ast.parse(code)
        self.generated_code.append(code)
        execution, self.execution = self.execution, None
        if execution is None:
            raise AssertionError("Unexpected Python execution")

        stdout = "Analysis result."
        files: dict[str, FileResult] = {}
        if execution == "image":
            stdout = "result.png"
            files[stdout] = {"description": "test image", "bytes": b"image"}
        elif execution == "table":
            stdout = "result.csv"
            files[stdout] = {
                "description": "test table",
                "bytes": b"column\nvalue\n",
            }
        return {"exit_code": 0, "stdout": stdout, "stderr": "", "files": files}

    def assert_complete(self) -> None:
        assert self.execution is None, "Expected Python execution did not occur"



class FakeMessages(MessageHandler):
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.images: list[str] = []
        self.tables: list[tuple[list[str], list[list[str]]]] = []

    async def send_text(self, channel_id: int, text: str) -> None:
        del channel_id
        self.texts.append(text)

    async def send_image(
            self,
            channel_id: int,
            filename: str,
            image_data: bytes,
    ) -> None:
        del channel_id, image_data
        self.images.append(filename)

    async def send_attachment(
            self,
            channel_id: int,
            filename: str,
            file_data: bytes,
    ) -> None:
        del channel_id, filename, file_data
        raise AssertionError("Unexpected attachment")

    async def send_table(
            self,
            channel_id: int,
            header: list[str],
            rows: list[list[str]],
    ) -> None:
        del channel_id
        self.tables.append((header, rows))

    async def add_reaction(
            self,
            channel_id: int,
            message_id: int,
            emoji: str,
    ) -> None:
        del channel_id, message_id, emoji
        raise AssertionError("Unexpected reaction")

    @asynccontextmanager
    async def typing(self, channel_id: int) -> AsyncIterator[None]:
        del channel_id
        yield



class ScriptedMessages:
    def __init__(self, turns: list[str]) -> None:
        self.turns = deque(enumerate(turns, start=1))

    async def __call__(self, timeout: int) -> Message | None:
        del timeout
        if not self.turns:
            return None
        message_id, content = self.turns.popleft()
        return {
            "guild_id": 1,
            "channel_name": "stats-test",
            "channel_id": 2,
            "author_id": 3,
            "author_name": "student",
            "author_mention": "@student",
            "message_id": message_id,
            "content": content,
            "files": [],
        }



async def record_nothing(*_args: object, **_kwargs: object) -> None:
    return None



def context() -> DuckContext:
    return DuckContext(1, 2, 3, "@student", "", 4, 5, 60)



def history(turns: list[dict]) -> list[HistoryType]:
    return [
        EasyInputMessageParam(role=turn["role"], content=turn["content"], type="message")
        for turn in turns
    ]
