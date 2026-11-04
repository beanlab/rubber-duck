import ast
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from openai.types.responses import EasyInputMessageParam
from pydantic import JsonValue

from src.duck_protocols import DuckContext, MessageHandler
from src.gen_ai.ai_responses import Agent, ResponsesAPI
from src.utils.config_types import HistoryType
from src.utils.protocols import Message
from src.utils.python_exec_container import ExecutionResult, FileResult, PythonExecContainer
from src.workflows.stats_duck.stats_duck_workflow import (
    INTRODUCTION,
    AnalysisOrder,
    DatasetOrder,
    Decision,
    PlotOrder,
    StatsOrder,
    StatsDuckWorkflow,
    _dataset_context,
    _stage_agent,
)
from tests.stats_duck.cases import (
    DatasetFixture,
    DecisionExpectation,
    ExecutionKind,
    HistoryTurn,
    StatsCase,
    TestSuite,
    TextExpectation,
)


ROOT = Path(__file__).resolve().parents[2]


class FakeSandbox(PythonExecContainer):
    def __init__(
            self,
            datasets: list[DatasetFixture],
            execution: ExecutionKind | None,
    ) -> None:
        self.datasets = datasets
        self.execution = execution
        self.generated_code: list[str] = []

    def get_dataset_inventory(self) -> list[dict[str, str]]:
        return [
            {"filename": item.filename, "dataset_name": item.dataset_name, "path": item.path}
            for item in self.datasets
        ]

    def describe_dataset(self, dataset_name: str) -> str | None:
        return next(
            (
                item.description
                for item in self.datasets
                if item.filename == dataset_name
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


@dataclass
class Harness:
    workflow: StatsDuckWorkflow
    sandbox: FakeSandbox
    messages: FakeMessages


def build_harness(
        suite: TestSuite,
        context_name: str,
        responses_api: ResponsesAPI,
        turns: list[str] | None = None,
        execution: ExecutionKind | None = None,
) -> Harness:
    agent = Agent(
        name="stats_test",
        model=suite.model,
        prompt=(ROOT / suite.base_prompt).read_text(encoding="utf-8"),
        reasoning=suite.reasoning,
    )
    sandbox = FakeSandbox(suite.contexts[context_name], execution)
    messages = FakeMessages()
    datasets = f"Available datasets and metadata:\n{_dataset_context(sandbox)}"
    workflow = StatsDuckWorkflow(
        name="stats_test",
        introduction=INTRODUCTION,
        decision_agent=_stage_agent(agent, "decision.md", datasets),
        order_agent=_stage_agent(agent, "order.md", datasets),
        coder_agent=_stage_agent(agent, "coder.md", datasets),
        clarification_agent=_stage_agent(agent, "clarification.md"),
        responses_api=responses_api,
        sandbox=sandbox,
        message_handler=messages,
        record_usage=record_nothing,
        record_message=record_nothing,
        wait_message=ScriptedMessages(turns or []),
    )
    return Harness(workflow, sandbox, messages)


def context() -> DuckContext:
    return DuckContext(1, 2, 3, "@student", "", 4, 5, 60)


def history(turns: list[HistoryTurn]) -> list[HistoryType]:
    return [
        EasyInputMessageParam(role=turn.role, content=turn.content, type="message")
        for turn in turns
    ]


def stats_order(value: dict[str, JsonValue]) -> StatsOrder:
    data, args = value.get("data"), value.get("args")
    if "action" in value:
        assert data is None or isinstance(data, str)
        if value["action"] == "list_datasets":
            return DatasetOrder(action="list_datasets", data=data)
        if value["action"] == "describe_dataset":
            return DatasetOrder(action="describe_dataset", data=data)
        raise AssertionError(f"Unsupported dataset action: {value['action']}")
    assert isinstance(data, (str, dict)) and isinstance(args, dict)
    if "plot" in value:
        return PlotOrder(plot=str(value["plot"]), data=data, args=args)
    return AnalysisOrder(data=data, analysis=str(value["analysis"]), args=args)


def assert_text(value: str, expected: TextExpectation) -> None:
    value = value.casefold()
    assert all(term.casefold() in value for term in expected.contains_all)
    assert all(term.casefold() not in value for term in expected.excludes)
    assert not expected.question or "?" in value


def assert_decision(result: Decision, expected: DecisionExpectation) -> None:
    assert result["analysis_requested"] is expected.analysis_requested
    if expected.analysis_description:
        assert_text(result["analysis_description"] or "", expected.analysis_description)
    if expected.missing_information:
        assert_text(result["missing_information"] or "", expected.missing_information)


def assert_workflow(case: StatsCase, harness: Harness) -> None:
    assert harness.sandbox.execution is None
    assert harness.messages.texts[0] == INTRODUCTION
    texts = harness.messages.texts[1:]
    assert len(texts) == len(case.expect.texts)
    for value, expected in zip(texts, case.expect.texts, strict=True):
        assert_text(value, expected)
    assert len(harness.messages.images) == case.expect.images
    assert len(harness.messages.tables) == case.expect.tables
    if case.expect.code:
        assert len(harness.sandbox.generated_code) == 1
        assert_text(harness.sandbox.generated_code[0], case.expect.code)
    else:
        assert not harness.sandbox.generated_code


async def run_case(
        suite: TestSuite,
        case: StatsCase,
        responses_api: ResponsesAPI,
) -> None:
    harness = build_harness(
        suite,
        case.context,
        responses_api,
        turns=case.turns,
        execution=case.execution,
    )
    if case.run == "full":
        await harness.workflow(context())
        assert_workflow(case, harness)
        return

    stages = [case.run] if isinstance(case.run, str) else case.run
    decision: Decision | None = None
    order: StatsOrder | None = None
    for stage in stages:
        if stage == "decision":
            decision = await harness.workflow._decide(context(), history(case.history))
            assert case.expect.decision is not None
            assert_decision(decision, case.expect.decision)
        elif stage == "order":
            description = case.analysis_description
            if decision is not None:
                description = decision["analysis_description"]
            assert description is not None
            order = await harness.workflow._order_from_menu(context(), description)
            assert order == case.expect.order
        else:
            if order is None:
                assert case.order is not None
                order = stats_order(case.order)
            code = await harness.workflow._generate_code(context(), order)
            ast.parse(code)
            assert case.expect.code is not None
            assert_text(code, case.expect.code)
