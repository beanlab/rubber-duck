import pytest

pytestmark = [
    pytest.mark.skip(reason="Function signatures only; implementation pending."),
    pytest.mark.anyio,
]


# Open through the real router and verify the thread link, stored owner, start marker, and greeting.
@pytest.mark.parametrize("duck", [], indirect=True)
async def test_conversation_start(duck, evaluation):
    ...


# Route successive messages in one thread and verify their replies and preserved history.
@pytest.mark.parametrize(
    ("duck", "scripted_responses", "turns", "expected_deliveries"), [], indirect=["duck"]
)
async def test_conversation_turns(
    duck, evaluation, run_conversation, turns, expected_deliveries
):
    ...


# Reopen the existing user thread and verify the previous conversation ends before a fresh greeting.
@pytest.mark.parametrize(("duck", "scripted_responses"), [], indirect=["duck"])
async def test_conversation_restart(duck, evaluation):
    ...


# Let a normal conversation time out and verify its end marker and workflow completion.
@pytest.mark.parametrize("duck", [], indirect=True)
async def test_conversation_completion(duck, evaluation):
    ...


# Persist actual user messages, agent outputs, and per-stage usage under the right conversation.
@pytest.mark.parametrize(
    ("duck", "scripted_responses", "expected_records"), [], indirect=["duck"]
)
async def test_conversation_records(duck, evaluation, run_conversation, expected_records):
    ...
