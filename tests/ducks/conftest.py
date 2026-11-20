from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

import pytest

from harness.application import build_duck, open_environment
from harness.application import run_conversation as execute_conversation
from harness.application import run_stage as execute_stage
from harness.experiment import load_inputs, validate_collection
from harness.results import record_pytest_outcome

if TYPE_CHECKING:
    from src.duck_protocols import DuckConversation
    from src.workflows.standard_duck.standard_duck_workflow import StandardDuckWorkflow
    from src.workflows.stats_duck.stats_duck_workflow import StatsDuckWorkflow


# Parametrize Rubber cases using test_rubber.load_cases before collection completes.
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
    ...


# Supply controlled model responses for offline tests without enabling live calls.
@pytest.fixture
def scripted_responses() -> list[dict]:
    ...


# Enter the harness environment with resolved inputs and yield its per-test services.
@pytest.fixture
async def evaluation(request, tmp_path, scripted_responses) -> AsyncIterator[dict]:
    ...


# Ask the harness to build the production Rubber workflow with this test's overrides.
@pytest.fixture
def rubber_duck(evaluation) -> StandardDuckWorkflow:
    ...


# Stage the known Stats data and ask the harness to build its production workflow.
@pytest.fixture
def stats_duck(evaluation, tmp_path) -> StatsDuckWorkflow:
    ...


# Select an existing Rubber or Stats fixture for shared application journey tests.
@pytest.fixture
def duck(request) -> DuckConversation:
    ...


# Bind this test's environment to the harness stage executor.
@pytest.fixture
def run_stage(evaluation) -> Callable[..., Awaitable[object]]:
    ...


# Bind this test's environment to the harness application conversation executor.
@pytest.fixture
def run_conversation(
    evaluation,
) -> Callable[[DuckConversation, list[str]], Awaitable[list[dict]]]:
    ...
