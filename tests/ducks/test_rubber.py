from pathlib import Path

import pytest

from harness.grading import evaluate_criteria

pytestmark = [
    pytest.mark.skip(reason="Function signatures only; implementation pending."),
    pytest.mark.anyio,
]


# Validate Rubber YAML and return cases with the fixed criteria for the requested scope.
def load_cases(path: Path, *, run: str = "response") -> list[dict]:
    ...


# Evaluate one production Rubber reply for the selected YAML case.
@pytest.mark.prompt_eval
async def test_response(rubber_duck, evaluation, run_stage, rubber_case):
    ...


# Evaluate a production Rubber conversation for the selected YAML case.
@pytest.mark.prompt_eval
async def test_workflow(rubber_duck, evaluation, run_conversation, rubber_case):
    ...


# Preserve user and assistant history across actual conversational turns with scripted model replies.
@pytest.mark.parametrize(
    ("turns", "scripted_responses", "expected_requests", "expected_deliveries"), []
)
async def test_conversation_history(
    rubber_duck, evaluation, run_conversation, turns, expected_requests, expected_deliveries
):
    ...
