import os
from pathlib import Path
from types import SimpleNamespace
from typing import AsyncIterator

import pytest
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.gen_ai.ai_responses import ResponsesAPI
from src.utils.config_types import RetryProtocol
from src.utils.config_loader import load_configuration
from src.workflows.stats_duck.stats_duck_workflow import build
from .fakes import FakeSandbox, FakeMessages, record_nothing


RETRY: RetryProtocol = {"max_retries": 0, "delay": 0, "backoff": 1}


@pytest.fixture
async def live_responses_api() -> AsyncIterator[ResponsesAPI]:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for live Stats Duck tests")
    async with AsyncOpenAI(timeout=60.0, max_retries=0) as client:
        yield ResponsesAPI(RETRY, client)


NUTRITION_DATASETS = [
    {
        "filename": "cereal.csv",
        "dataset_name": "Cereal Nutrition Data",
        "path": "/home/sandbox/datasets/cereal.csv",
        "description": "Dataset name: Cereal Nutrition Data\nColumns:\n- cereal, string, cereal name\n- calories, integer, calories per serving\n",
    },
    {
        "filename": "restaurant_nutrition.csv",
        "dataset_name": "Restaurant Nutrition Data",
        "path": "/home/sandbox/datasets/restaurant_nutrition.csv",
        "description": "Dataset name: Restaurant Nutrition Data\nColumns:\n- item, string, menu item\n- calories, integer, calories per item\n",
    },
]


# Build the production Stats workflow with controlled dataset metadata and delivery dependencies.
@pytest.fixture
def model_workflow(live_responses_api):
    settings = load_configuration(
        str(Path(__file__).resolve().parents[3] / "production-config.yaml")
    )["ducks"]["stats-duck"]["settings"]
    sandbox = FakeSandbox(NUTRITION_DATASETS, None)
    messages = FakeMessages()
    workflow = build(
        "stats_test",
        settings,
        message_handler=messages,
        metrics_handler=SimpleNamespace(
            record_message=record_nothing,
            record_usage=record_nothing,
            record_stats_cache_event=record_nothing,
        ),
        responses_api=live_responses_api,
        containers={"stats-python-sandbox": sandbox},
        sql_session=None,
        tool_configs={},
    )
    return workflow, sandbox, messages
