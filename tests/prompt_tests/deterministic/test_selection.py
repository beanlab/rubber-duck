import pytest

from src.gen_ai.decision import JevDecisionService
from experiments.evaluation.selection import CriterionDecisionEvaluator
from experiments.evaluation.types import (
    EvaluationTestConfig,
    EvaluatorContext,
    RubberDuckTestConfig,
)
from tests.prompt_tests.deterministic.support import FakeJevClient


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
            "selection": "conditional",
            "definition": "When the learner asks for a complete solution, does the tutor preserve student work?",
            "metric": {
                "pass": {"definition": "Preserves student work"},
                "fail": {"definition": "Gives the complete solution"},
            },
        },
        "learner_self_correction": {
            "selection": "conditional",
            "definition": "When a later learner turn is available, does the learner self-correct?",
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

    evaluator = CriterionDecisionEvaluator(JevDecisionService(client=client))
    result = await evaluator.evaluate(
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
        "applies::learner_self_correction",
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
