import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from openai import AsyncOpenAI
from openai.types.responses import EasyInputMessageParam, ResponseInputItemParam

from src.duck_protocols import DuckContext, MessageHandler
from src.gen_ai.ai_responses import Agent, ResponsesAPI
from src.utils.config_types import RetryProtocol
from src.utils.python_exec_container import ExecutionResult, PythonExecContainer
from src.workflows.stats_duck.stats_duck_workflow import (
    DatasetOrder,
    Decision,
    StatsDuckWorkflow,
    _dataset_context,
    _stage_agent,
)
from tests.stats_duck.cases import (
    ChainCase,
    ClarificationCase,
    DatasetFixture,
    DecisionCase,
    DecisionExpectation,
    FulfillmentCase,
    HistoryTurn,
    OrderCase,
    TextExpectation,
    load_suite,
)


ROOT = Path(__file__).resolve().parents[2]
SUITE = load_suite(Path(__file__).with_name("cases.yaml"))
RETRY: RetryProtocol = {"max_retries": 0, "delay": 0, "backoff": 1}


class FakeSandbox(PythonExecContainer):
    def __init__(self, datasets: list[DatasetFixture]) -> None:
        self._datasets = datasets

    def get_dataset_inventory(self) -> list[dict[str, str]]:
        return [
            {
                "filename": dataset.filename,
                "dataset_name": dataset.dataset_name,
                "path": dataset.path,
            }
            for dataset in self._datasets
        ]

    def describe_dataset(self, dataset_name: str) -> str | None:
        return next(
            (
                dataset.description
                for dataset in self._datasets
                if dataset.filename == dataset_name
            ),
            None,
        )

    async def run_code(self, code: str) -> ExecutionResult:
        del code
        raise AssertionError("This case must not execute Python")


class FakeMessages(MessageHandler):
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, channel_id: int, text: str) -> None:
        del channel_id
        self.sent.append(text)

    async def send_image(
            self, channel_id: int, filename: str, image_data: bytes,
    ) -> None:
        del channel_id, filename, image_data
        raise AssertionError("Unexpected image")

    async def send_attachment(
            self, channel_id: int, filename: str, file_data: bytes,
    ) -> None:
        del channel_id, filename, file_data
        raise AssertionError("Unexpected attachment")

    async def send_table(
            self,
            channel_id: int,
            header: list[str],
            rows: list[list[str]],
    ) -> None:
        del channel_id, header, rows
        raise AssertionError("Unexpected table")

    async def add_reaction(self, message_id: int, emoji: str) -> None:
        del message_id, emoji
        raise AssertionError("Unexpected reaction")

    def typing(self, channel_id: int) -> None:
        del channel_id


async def record_nothing(*_args: object, **_kwargs: object) -> None:
    return None


def history(turns: list[HistoryTurn]) -> list[ResponseInputItemParam]:
    items: list[ResponseInputItemParam] = []
    for turn in turns:
        message: EasyInputMessageParam = {
            "role": turn.role,
            "content": turn.content,
            "type": "message",
        }
        items.append(message)
    return items


def context() -> DuckContext:
    return DuckContext(1, 2, 3, "@student", "", 4, 5, 60)


def workflow(
        responses_api: ResponsesAPI,
        context_name: str,
) -> StatsDuckWorkflow:
    prompt = (ROOT / SUITE.base_prompt).read_text(encoding="utf-8")
    sandbox = FakeSandbox(SUITE.contexts[context_name])
    agent = Agent(
        name="stats_test",
        model=SUITE.model,
        prompt=prompt,
        reasoning=SUITE.reasoning,
    )
    dataset_prompt = (
        f"Available datasets and metadata:\n{_dataset_context(sandbox)}"
    )
    return StatsDuckWorkflow(
        name="stats_test",
        introduction="",
        decision_agent=_stage_agent(agent, "decision.md", dataset_prompt),
        order_agent=_stage_agent(agent, "order.md", dataset_prompt),
        coder_agent=_stage_agent(agent, "coder.md", dataset_prompt),
        clarification_agent=_stage_agent(agent, "clarification.md"),
        responses_api=responses_api,
        sandbox=sandbox,
        message_handler=FakeMessages(),
        record_usage=record_nothing,
        record_message=record_nothing,
    )


def assert_text(value: str | None, expected: TextExpectation) -> None:
    assert value is not None
    lowered = value.casefold()
    for term in expected.contains_all:
        assert term.casefold() in lowered
    for term in expected.excludes:
        assert term.casefold() not in lowered
    if expected.question:
        assert "?" in value


def assert_decision(
        result: Decision,
        expected: DecisionExpectation,
) -> None:
    assert result["analysis_requested"] is expected.analysis_requested
    if expected.analysis_description is not None:
        description = result["analysis_description"]
        assert isinstance(description, str)
        assert_text(description, expected.analysis_description)
    if expected.missing_information is not None:
        missing = result["missing_information"]
        assert isinstance(missing, str)
        assert_text(missing, expected.missing_information)


def live_client() -> AsyncOpenAI:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for live Stats Duck tests")
    return AsyncOpenAI()


def dataset_order(case: FulfillmentCase) -> DatasetOrder:
    action = case.order.get("action")
    data = case.order.get("data")
    assert data is None or isinstance(data, str)
    if action == "list_datasets":
        return {"action": "list_datasets", "data": data}
    if action == "describe_dataset":
        return {"action": "describe_dataset", "data": data}
    raise AssertionError(f"Unsupported dataset action: {action}")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.prompt_eval
@pytest.mark.parametrize(
    "case", SUITE.decisions, ids=[case.id for case in SUITE.decisions],
)
async def test_decide(case: DecisionCase) -> None:
    async with live_client() as client:
        result = await workflow(
            ResponsesAPI(RETRY, client), case.context,
        )._decide(context(), history(case.history))

    assert_decision(result, case.expect)


@pytest.mark.anyio
@pytest.mark.prompt_eval
@pytest.mark.parametrize(
    "case", SUITE.orders, ids=[case.id for case in SUITE.orders],
)
async def test_order(case: OrderCase) -> None:
    async with live_client() as client:
        result = await workflow(
            ResponsesAPI(RETRY, client), case.context,
        )._order_from_menu(context(), case.analysis_description)

    assert result == case.expect


@pytest.mark.anyio
@pytest.mark.prompt_eval
@pytest.mark.parametrize(
    "case", SUITE.clarifications, ids=[case.id for case in SUITE.clarifications],
)
async def test_clarification(case: ClarificationCase) -> None:
    async with live_client() as client:
        response = await workflow(
            ResponsesAPI(RETRY, client), case.context,
        )._help_user_towards_a_decision(
            context(), history(case.history), case.missing_information,
        )

    result = response["result"]
    assert isinstance(result, str)
    assert_text(result, case.expect)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "case", SUITE.fulfillments, ids=[case.id for case in SUITE.fulfillments],
)
async def test_fulfillment(case: FulfillmentCase) -> None:
    async with AsyncOpenAI(api_key="unused") as client:
        result = await workflow(
            ResponsesAPI(RETRY, client), case.context,
        )._fulfill_order(context(), dataset_order(case))

    assert result == case.expect


@pytest.mark.anyio
@pytest.mark.prompt_eval
@pytest.mark.parametrize(
    "case", SUITE.chains, ids=[case.id for case in SUITE.chains],
)
async def test_chain_to_fulfillment(case: ChainCase) -> None:
    async with live_client() as client:
        duck = workflow(ResponsesAPI(RETRY, client), case.context)
        decision = await duck._decide(context(), history(case.history))
        assert_decision(decision, case.expect.decision)

        if decision["analysis_requested"]:
            description = decision["analysis_description"]
            assert isinstance(description, str)
            order = await duck._order_from_menu(context(), description)
            assert order == case.expect.order
            return

        missing = decision["missing_information"]
        assert isinstance(missing, str)
        response = await duck._help_user_towards_a_decision(
            context(), history(case.history), missing,
        )
        result = response["result"]
        assert isinstance(result, str)
        assert case.expect.clarification is not None
        assert_text(result, case.expect.clarification)
