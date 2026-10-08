from collections.abc import Mapping

import pytest
from typesafe_sdk import JSONContent, Question, SystemOneResponse

from src.testing.prompt_evaluation.jev import JevEvaluator
from src.testing.prompt_evaluation.types import (
    EvaluationTestConfig,
    EvaluatorContext,
    RubberDuckTestConfig,
)


class FakeJevClient:
    def __init__(self) -> None:
        self.states: list[JSONContent] = []
        self.questions: list[dict[str, Question]] = []
        self.models: list[str | None] = []

    async def system_one(
        self,
        state: JSONContent,
        questions: Mapping[str, Question],
        *,
        model: str | None = None,
    ) -> SystemOneResponse:
        self.states.append(state)
        self.questions.append(dict(questions))
        self.models.append(model)
        answers: dict[str, object] = {}
        for name in questions:
            if name == "applies::solution_boundary":
                answers[name] = {
                    "type": "choice",
                    "choice": "applicable",
                    "confidence": 0.8,
                    "probabilities": {
                        "applicable": 0.9,
                        "not_applicable": 0.05,
                        "insufficient_evidence": 0.05,
                    },
                }
            else:
                rating = "fail" if name == "grade::guidance" else "pass"
                answers[name] = {
                    "type": "choice",
                    "choice": rating,
                    "confidence": 0.8,
                    "probabilities": {
                        "pass": 0.9 if rating == "pass" else 0.2,
                        "fail": 0.1 if rating == "pass" else 0.8,
                    },
                }
        return SystemOneResponse.model_validate(
            {"model": "jev-test", "usage": {}, "answers": answers}
        )


@pytest.mark.anyio
async def test_jev_selects_then_evaluates_only_selected_tests() -> None:
    tests: dict[str, EvaluationTestConfig] = {
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
    }
    rubber_duck_tests: dict[str, RubberDuckTestConfig] = {
        "solution_boundary": {
            "scope": "response",
            "oracle": "semantic",
            "selection": "conditional",
            "applies_when": "The learner asks for a complete solution.",
            "definition": "Does the tutor preserve student work?",
            "metric": {
                "pass": {"definition": "Preserves student work"},
                "fail": {"definition": "Gives the complete solution"},
            },
        },
        "learner_self_correction": {
            "scope": "trajectory",
            "oracle": "semantic",
            "selection": "conditional",
            "applies_when": "A later learner turn is available.",
            "definition": "Does the learner self-correct?",
            "metric": {
                "pass": {"definition": "Learner self-corrects"},
                "fail": {"definition": "Learner does not self-correct"},
            },
        },
    }
    context: EvaluatorContext = {
        "conversation_prefix": [
            {"role": "student", "message": "Give me the full solution."}
        ],
        "candidate_response": {"role": "tutor", "message": "Try this."},
        "candidate_action": "talk_to_user",
        "tutor_prompt": "Tutor prompt",
    }
    client = FakeJevClient()

    result = await JevEvaluator(client=client).evaluate(
        context,
        tests,
        {"accuracy": "standard", "guidance": "case"},
        rubber_duck_tests,
        "Judge only the candidate response.",
    )

    assert client.models == ["jev-latest", "jev-latest"]
    assert len(client.questions) == 2
    assert set(client.questions[0]) == {
        "applies::solution_boundary",
    }
    assert set(client.questions[1]) == {
        "grade::accuracy",
        "grade::guidance",
        "grade::solution_boundary",
    }
    assert result["selection"]["selected"] == ["solution_boundary"]
    assert result["selection"]["skipped"] == ["learner_self_correction"]
    assert result["selection"]["uncertain"] == []
    assert result["tests"]["accuracy"]["rating"] == "pass"
    assert result["tests"]["accuracy"]["suite"] == "standard"
    assert result["tests"]["guidance"]["rating"] == "fail"
    assert result["tests"]["guidance"]["suite"] == "case"
    assert result["tests"]["solution_boundary"]["rating"] == "pass"
    assert result["tests"]["solution_boundary"]["suite"] == "rubber_duck"
    assert result["summary"]["passed"] is False
    assert result["summary"]["score"] == pytest.approx(2 / 3)
    assert result["summary"]["blocking_tests"] == ["guidance"]
