from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

import pytest

from tests.workflows.application import build_duck, open_environment
from tests.workflows.application import run_conversation as execute_conversation
from tests.workflows.application import run_stage as execute_stage
from evaluation.experiment import load_inputs, validate_collection
from evaluation.results import record_pytest_outcome

if TYPE_CHECKING:
    from src.duck_protocols import DuckConversation
    from src.workflows.standard_duck.standard_duck_workflow import StandardDuckWorkflow
    from src.workflows.stats_duck.stats_duck_workflow import StatsDuckWorkflow


# Parametrize Standard cases using standard_duck.cases.load_cases before collection completes.
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    ...


# Delegate verification of the collected case IDs to the experiment plan validator.
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    ...


# Forward selected pytest phase outcomes to the harness evidence recorder.
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    ...


# Use asyncio for the application's asynchronous tests.
@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# Supply controlled model responses for offline tests without enabling live calls.
@pytest.fixture
def scripted_responses() -> list[dict]:
    ...


# Enter the shared test environment with resolved inputs and yield its per-test services.
@pytest.fixture
async def evaluation(request, tmp_path, scripted_responses) -> AsyncIterator[dict]:
    ...


# Use the shared application driver to build Standard Duck with this test's overrides.
@pytest.fixture
def standard_duck(evaluation) -> StandardDuckWorkflow:
    ...


# Stage known Stats data and use the shared application driver to build its production workflow.
@pytest.fixture
def stats_duck(evaluation, tmp_path) -> StatsDuckWorkflow:
    ...


# Select an existing Standard or Stats fixture for shared application journey tests.
@pytest.fixture
def duck(request) -> DuckConversation:
    ...


# Bind this test's environment to the shared stage executor.
@pytest.fixture
def run_stage(evaluation) -> Callable[..., Awaitable[object]]:
    ...


# Bind this test's environment to the shared application conversation executor.
@pytest.fixture
def run_conversation(
    evaluation,
) -> Callable[[DuckConversation, list[str]], Awaitable[list[dict]]]:
    ...
