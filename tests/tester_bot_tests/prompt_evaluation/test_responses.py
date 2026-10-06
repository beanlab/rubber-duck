"""Run the live fixed-prefix tutor-response experiment.

Each YAML case supplies a model-visible conversation prefix and an
evaluator-only reference answer. The test makes one model call to generate the
next tutor response and another to grade that response using the criteria in
``config.yaml``. It prints the response, ratings, and rationales when pytest is
run with ``-s``.

This is diagnostic evaluation, not a quality gate: the assertion checks that
all configured criteria were returned, not that their ratings are acceptable.
It also evaluates only the next response conditional on the supplied prefix;
it does not establish how the prompt would conduct the complete conversation.
"""

import os
from pathlib import Path

import pytest
import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.testing.tutor_response_evaluation import (
    evaluate_next_response,
    print_evaluation,
)


TEST_ROOT = Path(__file__).resolve().parent
ROOT = TEST_ROOT.parents[2]
EVALUATION_CONFIG = TEST_ROOT / "config.yaml"
CASES_CONFIG = TEST_ROOT / "cases.yaml"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


CASES = load_yaml(CASES_CONFIG)["cases"]


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_prompt_response(case):
    """Generate one response and report only the configured criterion ratings."""
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for prompt response evaluations.")

    config = {**load_yaml(EVALUATION_CONFIG), **case}
    tutor_prompt = (ROOT / config["prompt_path"]).read_text(encoding="utf-8")
    result = await evaluate_next_response(
        client=AsyncOpenAI(),
        config=config,
        transcript=case["transcript"],
        tutor_prompt=tutor_prompt,
    )

    print(f"\nTutor response: {result['transcript'][-1]['message']}")
    print_evaluation(result)
    assert set(result["criteria"]) == set(config["criteria"])
