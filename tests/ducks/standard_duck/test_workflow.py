import pytest

from evaluation.grading import evaluate_criteria

pytestmark = [
    pytest.mark.skip(reason="Function signatures only; implementation pending."),
    pytest.mark.anyio,
]


# Greet once, seed the Hi/greeting history, and wait without submitting the opener to the model.
async def test_greeting_history(standard_duck, evaluation):
    ...


# Preserve prior user and assistant turns in each subsequent production model request.
@pytest.mark.parametrize(
    ("turns", "scripted_responses", "expected_requests", "expected_deliveries"), []
)
async def test_conversation_history(
    standard_duck, evaluation, run_conversation, turns, expected_requests, expected_deliveries
):
    ...


# Deliver nonempty agent results to the conversation thread after completing the typing context.
@pytest.mark.parametrize(("scripted_responses", "expected_deliveries"), [])
async def test_response_delivery(
    standard_duck, evaluation, run_conversation, expected_deliveries
):
    ...


# Record user text, assistant content, and function-call outputs under the correct conversation.
@pytest.mark.parametrize(("scripted_responses", "expected_records"), [])
async def test_message_records(
    standard_duck, evaluation, run_conversation, expected_records
):
    ...


# Persist available token usage once per turn and handle responses without usage information.
@pytest.mark.parametrize(("scripted_responses", "expected_usage"), [])
async def test_usage_records(
    standard_duck, evaluation, run_conversation, expected_usage
):
    ...


# Notify the user about a provider retry and deliver the eventual answer without duplicating the turn.
@pytest.mark.parametrize(("scripted_responses", "expected_deliveries"), [])
async def test_retry_notification(
    standard_duck, evaluation, run_conversation, expected_deliveries
):
    ...


# Return accumulated history when waiting times out without making another provider request.
@pytest.mark.parametrize(("turns", "scripted_responses", "expected_history"), [])
async def test_timeout_history(
    standard_duck, evaluation, run_conversation, turns, expected_history
):
    ...


# Reuse the configured duck for another conversation while starting its model history afresh.
@pytest.mark.parametrize(("scripted_responses", "expected_requests"), [])
async def test_fresh_conversation_history(
    standard_duck, evaluation, run_conversation, expected_requests
):
    ...


# Evaluate live tutoring behavior across every turn of a declared Standard Duck conversation case.
@pytest.mark.prompt_eval
async def test_workflow(standard_duck, evaluation, run_conversation, standard_case):
    ...
