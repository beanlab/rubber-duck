from types import SimpleNamespace
from typing import cast

import pytest

from src.testing.prompt_evaluation.jev import JevEvaluator
from src.testing.prompt_evaluation.types import (
    EvaluationConfig,
    EvaluationTestConfig,
    EvaluatorContext,
)


class FakeJevClient:
    def __init__(self) -> None:
        self.call = None

    async def system_one(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(
            model="jev-test",
            choices={
                "accuracy": SimpleNamespace(
                    choice="pass",
                    confidence=0.8,
                    probabilities={"pass": 0.9, "fail": 0.1},
                ),
                "guidance": SimpleNamespace(
                    choice="fail",
                    confidence=0.6,
                    probabilities={"pass": 0.2, "fail": 0.8},
                ),
            },
        )


@pytest.mark.anyio
async def test_jev_evaluates_all_tests_in_one_call() -> None:
    tests = cast(
        dict[str, EvaluationTestConfig],
        {
            "accuracy": {
                "definition": "Is it accurate?",
                "metric": {
                    "pass": {"definition": "Accurate"},
                    "fail": {"definition": "Inaccurate"},
                },
            },
            "guidance": {
                "definition": "Is the guidance useful?",
                "metric": {
                    "pass": {"definition": "Useful"},
                    "fail": {"definition": "Not useful"},
                },
            },
        },
    )
    config = cast(
        EvaluationConfig,
        {
            "evaluator_model": "openai-test",
            "evaluator_prompt": "Judge only the candidate response.",
            "tests": tests,
        },
    )
    context = cast(
        EvaluatorContext,
        {
            "conversation_prefix": [],
            "candidate_response": {"role": "tutor", "message": "Try this."},
            "tutor_prompt": "Tutor prompt",
        },
    )
    client = FakeJevClient()

    result = await JevEvaluator(client=client).evaluate(context, config, tests)

    assert client.call["state"] == context
    assert client.call["model"] == "jev-latest"
    assert set(client.call["questions"]) == set(tests)
    accuracy = client.call["questions"]["accuracy"]
    assert accuracy.instructions == {
        "test": "Is it accurate?",
        "rules": "Judge only the candidate response.",
    }
    assert accuracy.criteria == {"pass": "Accurate", "fail": "Inaccurate"}
    assert result["model"] == "jev-test"
    assert result["tests"]["accuracy"] == {
        "rating": "pass",
        "confidence": 0.8,
        "probabilities": {"pass": 0.9, "fail": 0.1},
    }
    assert result["summary"] == {
        "passed": False,
        "score": 0.5,
        "blocking_tests": ["guidance"],
    }
