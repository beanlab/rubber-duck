"""Evaluate one Rubber Duck response after each fixed conversation prefix."""

import os
from pathlib import Path

import pytest
import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.testing.prompt_evaluation import (
    evaluate_next_response,
    print_evaluation,
)


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path(__file__).resolve().parent
EVALUATION_CONFIG = ROOT / "evaluation_assets" / "prompt_eval.yaml"
CASES_CONFIG = TEST_ROOT / "prompt_cases.yaml"


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
