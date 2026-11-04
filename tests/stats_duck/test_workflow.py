from pathlib import Path

import pytest

from src.gen_ai.ai_responses import ResponsesAPI
from tests.stats_duck.cases import StatsCase, load_suite
from tests.stats_duck.harness import run_case


SUITE = load_suite(Path(__file__).with_name("cases.yaml"))


@pytest.mark.anyio
@pytest.mark.prompt_eval
@pytest.mark.parametrize("case", SUITE.cases, ids=[case.id for case in SUITE.cases])
async def test_case(case: StatsCase, live_responses_api: ResponsesAPI) -> None:
    await run_case(SUITE, case, live_responses_api)
