import asyncio
import json
from types import SimpleNamespace

from src.testing.prompt_evaluation import (
    CriterionResult,
    PromptEvaluation,
    build_tutor_history,
    evaluate_next_response,
)


class FakeOpenAIClient:
    def __init__(self):
        self.responses = self
        self.create_params = None
        self.parse_params = None

    async def create(self, **params):
        self.create_params = params
        call = SimpleNamespace(
            type="function_call",
            name="talk_to_user",
            arguments=json.dumps(
                {"message_to_user": "What output does the assignment require?"}
            ),
        )
        return SimpleNamespace(output=[call], output_text="")

    async def parse(self, **params):
        self.parse_params = params
        evaluation = PromptEvaluation(
            subject_accuracy=CriterionResult(
                rating="correct",
                evidence=["What output does the assignment require?"],
                rationale="The response makes no incorrect technical claim.",
            ),
            misconception_diagnosis=CriterionResult(
                rating="insufficient_evidence",
                evidence=[],
                rationale="The prefix does not establish a misconception.",
            ),
            guidance_scaffolding=CriterionResult(
                rating="useful",
                evidence=["What output does the assignment require?"],
                rationale="The response asks for necessary task information.",
            ),
            answer_disclosure=CriterionResult(
                rating="appropriate",
                evidence=["What output does the assignment require?"],
                rationale="The response does not disclose a solution.",
            ),
            relevance=CriterionResult(
                rating="relevant",
                evidence=["What output does the assignment require?"],
                rationale="The response addresses the learner's request.",
            ),
            actionability=CriterionResult(
                rating="actionable",
                evidence=["What output does the assignment require?"],
                rationale="The learner can provide the requested information.",
            ),
        )
        return SimpleNamespace(output_parsed=evaluation)


def test_evaluates_exactly_one_response_after_a_fixed_prefix():
    prefix = [
        {"role": "student", "message": "I need help."},
        {"role": "tutor", "message": "What have you tried?"},
        {"role": "student", "message": "I do not know where to start."},
    ]
    criteria = {
        name: {}
        for name in (
            "subject_accuracy",
            "misconception_diagnosis",
            "guidance_scaffolding",
            "answer_disclosure",
            "relevance",
            "actionability",
        )
    }
    config = {
        "model": "test-model",
        "evaluator_model": "test-evaluator-model",
        "reference_answer": "Identify the required output first.",
        "criteria": criteria,
        "evaluator_prompt": "Evaluate the response.",
    }
    client = FakeOpenAIClient()

    result = asyncio.run(
        evaluate_next_response(
            client=client,
            config=config,
            transcript=prefix,
            tutor_prompt="Tutor prompt",
        )
    )

    assert result["transcript"][-1] == {
        "role": "tutor",
        "message": "What output does the assignment require?",
    }
    assert result["reference_answer_used"] is True
    assert set(result["criteria"]) == set(criteria)
    assert client.create_params["input"] == build_tutor_history(prefix)
    assert client.parse_params["model"] == "test-evaluator-model"

    evaluator_input = json.loads(client.parse_params["input"])
    assert evaluator_input["conversation_prefix"] == prefix
    assert evaluator_input["candidate_response"] == result["transcript"][-1]
    assert evaluator_input["reference_answer"] == config["reference_answer"]
