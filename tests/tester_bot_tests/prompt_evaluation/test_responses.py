"""Run the live fixed-prefix tutor-response experiment.

Each YAML case supplies a model-visible conversation prefix and an
evaluator-only reference answer. The test generates one tutor response, then
runs every independent evaluation test configured in ``config.yaml`` against
that same response. It prints case and prompt-level measurements with ``-s``.

Configured metric outcomes determine whether each case passes. The experiment
still evaluates only the next response conditional on the supplied prefix; it
does not establish how the prompt would conduct the complete conversation.
"""

import os
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest
import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.build import build_agent
from src.testing.prompt_evaluation.evaluation import evaluate_next_response
from src.testing.prompt_evaluation.reporting import (
    evaluation_failure_message,
    print_case_evaluation,
    print_prompt_summary,
)
from src.testing.prompt_evaluation.types import (
    EvaluationCase,
    EvaluationConfig,
    EvaluationRun,
)
from src.utils.config_loader import load_configuration


TEST_ROOT = Path(__file__).resolve().parent
ROOT = TEST_ROOT.parents[2]
EVALUATION_CONFIG_PATH = TEST_ROOT / "config.yaml"
CASES_CONFIG = TEST_ROOT / "cases.yaml"


def load_yaml(path: Path) -> object:
    return cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))


config_data = load_yaml(EVALUATION_CONFIG_PATH)
cases_data = load_yaml(CASES_CONFIG)
if not isinstance(config_data, dict) or not isinstance(cases_data, dict):
    raise TypeError("Evaluation configuration files must contain YAML mappings")

SHARED_CONFIG = cast(EvaluationConfig, config_data)
CASES = cast(list[EvaluationCase], cases_data["cases"])
PROMPT_RESULTS: list[EvaluationRun] = []


async def _send_message(*_args: object, **_kwargs: object) -> int:
    return 1


application_config = load_configuration(str(ROOT / "production-config.yaml"))
STANDARD_AGENT = build_agent(
    application_config["ducks"]["standard-rubber-duck"]["settings"]["agent"]
)
STANDARD_ARMORY = Armory(_send_message)
STANDARD_ARMORY.scrub_tools(TalkTool(_send_message))


@pytest.fixture(scope="module", autouse=True)
def report_prompt_summary() -> Generator[None, None, None]:
    """Print aggregate measurements after all configured cases finish."""
    PROMPT_RESULTS.clear()
    yield
    if PROMPT_RESULTS:
        print_prompt_summary(PROMPT_RESULTS)


def case_id(case: EvaluationCase) -> str:
    return case["id"]


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=case_id)
async def test_prompt_response(case: EvaluationCase) -> None:
    """Generate one response and apply every configured evaluation test."""
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for prompt response evaluations.")

    config: EvaluationConfig = {
        **SHARED_CONFIG,
        "reference_answer": case["reference_answer"],
    }
    async with AsyncOpenAI() as client:
        result = await evaluate_next_response(
            client=client,
            config=config,
            transcript=case["transcript"],
            agent=STANDARD_AGENT,
            armory=STANDARD_ARMORY,
        )

    PROMPT_RESULTS.append(result)
    print_case_evaluation(case, result)

    if not result["summary"]["passed"]:
        pytest.fail(
            evaluation_failure_message(result),
            pytrace=False,
        )
