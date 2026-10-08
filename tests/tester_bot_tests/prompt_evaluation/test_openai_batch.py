import json

from pydantic import TypeAdapter

from src.testing.prompt_evaluation.evaluation import PreparedEvaluation
from src.testing.prompt_evaluation.openai_batch import (
    BatchRequestLine,
    build_batch_input,
)
from src.testing.prompt_evaluation.types import (
    EvaluationTestConfig,
    EvaluatorContext,
    EvaluatorRequest,
)


def test_batch_contains_only_preselected_semantic_tests() -> None:
    selected: dict[str, EvaluationTestConfig] = {
        "factual_correctness": {
            "definition": "Is it correct?",
            "metric": {
                "pass": {"definition": "Correct"},
                "fail": {"definition": "Incorrect"},
            },
        },
        "solution_boundary": {
            "definition": "Does it preserve student work?",
            "metric": {
                "pass": {"definition": "Preserves student work"},
                "fail": {"definition": "Gives away the solution"},
            },
        },
    }
    context: EvaluatorContext = {
        "conversation_prefix": [{"role": "student", "message": "Help."}],
        "candidate_response": {"role": "tutor", "message": "What have you tried?"},
        "candidate_action": "talk_to_user",
        "tutor_prompt": "Tutor prompt",
    }
    prepared = PreparedEvaluation(
        transcript=[*context["conversation_prefix"], context["candidate_response"]],
        candidate_action="talk_to_user",
        candidate_model="candidate-model",
        evaluator_model="evaluator-model",
        evaluator_prompt="Evaluate every supplied test.",
        evaluator_input=context,
        semantic_tests=selected,
        semantic_suites={
            "factual_correctness": "standard",
            "solution_boundary": "rubber_duck",
        },
        deterministic_results={},
        reference_answer_used=False,
        selection=None,
        jev=None,
    )

    line = TypeAdapter(BatchRequestLine).validate_json(
        build_batch_input([prepared]).decode().strip()
    )
    evaluator_input = line["body"]["input"]
    assert isinstance(evaluator_input, str)
    request = TypeAdapter(EvaluatorRequest).validate_json(evaluator_input)

    assert line["url"] == "/v1/responses"
    assert line["body"]["model"] == "evaluator-model"
    assert [test["name"] for test in request["tests"]] == [
        "factual_correctness",
        "solution_boundary",
    ]
    assert "not_selected" not in json.dumps(line)
