import os
from typing import AsyncIterator

import pytest
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.gen_ai.ai_responses import ResponsesAPI
from src.utils.config_types import RetryProtocol


RETRY: RetryProtocol = {"max_retries": 0, "delay": 0, "backoff": 1}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def live_responses_api() -> AsyncIterator[ResponsesAPI]:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for live Stats Duck tests")
    async with AsyncOpenAI(timeout=60.0, max_retries=0) as client:
        yield ResponsesAPI(RETRY, client)
