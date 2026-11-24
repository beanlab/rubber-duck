"""Run the live fixed-prefix tutor-response experiment.

Each YAML case supplies a model-visible conversation prefix and an
evaluator-only reference answer. The test generates one tutor response, uses
JEV to select applicable Standard Duck criteria, and evaluates the selected
criteria against that response. It prints case and prompt-level measurements
with ``-s``.

Every selected, standard, and case-specific criterion must pass for a case to pass. The
experiment still evaluates only the next response conditional on the supplied
prefix; it does not establish how the prompt would conduct the complete
conversation.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from openai import AsyncOpenAI
from typesafe_sdk import AsyncTypeSafeClient

from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.build import build_agent
from src.gen_ai.jev_responses import JevAPI
from evaluation.standard_duck.config import case_configuration, load_evaluation_suite
from evaluation.standard_duck.responses import evaluate_next_response
from evaluation.standard_duck.console import (
    evaluation_failure_message,
    print_case_evaluation,
)
from evaluation.standard_duck.selection import CriterionDecisionEvaluator
from evaluation.standard_duck.types import (
    EvaluationCase,
    EvaluationRun,
)
from evaluation.grading import evaluate_criteria
from src.utils.config_loader import load_configuration


TEST_ROOT = Path(__file__).resolve().parent
ROOT = TEST_ROOT.parents[2]
SUITE = load_evaluation_suite(TEST_ROOT / "configs")


async def _send_message(*_args: object, **_kwargs: object) -> int:
    return 1


application_config = load_configuration(str(ROOT / "production-config.yaml"))
STANDARD_AGENT = build_agent(
    application_config["ducks"]["standard-rubber-duck"]["settings"]["agent"]
)
STANDARD_ARMORY = Armory(_send_message)
STANDARD_ARMORY.scrub_tools(TalkTool(_send_message))


def case_id(case: EvaluationCase) -> str:
    return case["id"]


@pytest.mark.anyio
@pytest.mark.prompt_eval
@pytest.mark.parametrize("case", SUITE.cases, ids=case_id)
async def test_prompt_response(
    case: EvaluationCase,
    prompt_case_results: list[tuple[EvaluationCase, EvaluationRun]],
) -> None:
    """Generate one response and apply every configured evaluation test."""
    load_dotenv()
    openai_key = os.getenv("OPENAI_API_KEY")
    jev_key = os.getenv("JEV_API_KEY")
    if not openai_key or not jev_key:
        pytest.skip(
            "OPENAI_API_KEY and JEV_API_KEY are required for live prompt evaluations."
        )

    config = case_configuration(SUITE.config, case)
    async with (
        AsyncOpenAI(api_key=openai_key) as client,
        AsyncTypeSafeClient(api_key=jev_key) as jev_client,
    ):
        result = await evaluate_next_response(
            client=client,
            config=config,
            transcript=case["transcript"],
            agent=STANDARD_AGENT,
            armory=STANDARD_ARMORY,
            jev_evaluator=CriterionDecisionEvaluator(
                JevAPI(jev_client),
                model=config.get("jev_model", "jev-latest"),
            ),
            rubber_duck_tests=SUITE.rubber_duck_tests,
        )

    prompt_case_results.append((case, result))
    print_case_evaluation(case, result)

    if not result["summary"]["passed"]:
        pytest.fail(
            evaluation_failure_message(result),
            pytrace=False,
        )


# Resolve production prompt files, model, and reasoning settings without changing shared defaults.
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
@pytest.mark.anyio
@pytest.mark.parametrize("expected_agent", [])
async def test_agent_configuration(standard_duck, evaluation, expected_agent):
    ...


# Evaluate a production agent turn against fixed history and the selected case's tutoring criteria.
@pytest.mark.skip(reason="Function signatures only; implementation pending.")
@pytest.mark.anyio
@pytest.mark.prompt_eval
async def test_response(standard_duck, evaluation, run_stage, standard_case):
    ...
