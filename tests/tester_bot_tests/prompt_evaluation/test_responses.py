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
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import TypeAdapter

from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.build import build_agent
from src.testing.prompt_evaluation.evaluation import evaluate_next_response
from src.testing.prompt_evaluation.jev import JevEvaluator
from src.testing.prompt_evaluation.reporting import (
    evaluation_failure_message,
    print_case_evaluation,
    print_prompt_summary,
)
from src.testing.prompt_evaluation.types import (
    EvaluationCase,
    EvaluationCasesFile,
    EvaluationConfig,
    EvaluationRun,
    RubberDuckTestsConfig,
)
from src.utils.config_loader import load_configuration


TEST_ROOT = Path(__file__).resolve().parent
ROOT = TEST_ROOT.parents[2]
EVALUATION_CONFIG_PATH = TEST_ROOT / "config.yaml"
CASES_CONFIG = TEST_ROOT / "cases.yaml"
RUBBER_DUCK_TESTS_CONFIG = TEST_ROOT / "rubber_duck_tests.yaml"


def load_yaml(path: Path) -> object:
    data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


SHARED_CONFIG = TypeAdapter(EvaluationConfig).validate_python(
    load_yaml(EVALUATION_CONFIG_PATH)
)
CASES = TypeAdapter(EvaluationCasesFile).validate_python(load_yaml(CASES_CONFIG))[
    "cases"
]
RUBBER_DUCK_TESTS = TypeAdapter(RubberDuckTestsConfig).validate_python(
    load_yaml(RUBBER_DUCK_TESTS_CONFIG)
)["rubber_duck_tests"]
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

    config = SHARED_CONFIG.copy()
    config["reference_answer"] = case["reference_answer"]
    config["case_tests"] = case.get("tests", {})
    async with AsyncOpenAI() as client:
        jev_key = os.getenv("JEV_API_KEY")
        result = await evaluate_next_response(
            client=client,
            config=config,
            transcript=case["transcript"],
            agent=STANDARD_AGENT,
            armory=STANDARD_ARMORY,
            jev_evaluator=(
                JevEvaluator(
                    api_key=jev_key,
                    model=config.get("jev_model", "jev-latest"),
                )
                if jev_key
                else None
            ),
            rubber_duck_tests=RUBBER_DUCK_TESTS,
        )

    PROMPT_RESULTS.append(result)
    print_case_evaluation(case, result)

    if not result["summary"]["passed"]:
        pytest.fail(
            evaluation_failure_message(result),
            pytrace=False,
        )
