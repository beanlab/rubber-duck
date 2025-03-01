import pytest

from rubber_duck.sql_metrics import SQLMetricsHandler, create_sqlite_session

testValuesDict = {
    "guild_id": 1234,
    "thread_id": 5678,
    "user_id": 123456789,
    "role": "test-role",
    "message": "test-message",
    "engine": "test-engine",
    "input_tokens": "test-input-token",
    "output_tokens": "test-output-token",
    "reviewer_role_id": 987654,
    "feedback_score": 4
}

session = create_sqlite_session('sqlite:///:memory:')
sql_handler = SQLMetricsHandler(session)


@pytest.mark.asyncio
async def test_messages_table():
    # Record message to the memory database
    await sql_handler.record_message(testValuesDict["guild_id"], testValuesDict["thread_id"], testValuesDict["user_id"],
                                     testValuesDict["role"], testValuesDict["message"])

    # Retrieve the recorded messages from the memory database
    recorded_messages = sql_handler.get_message()

    assert recorded_messages is not None
    assert recorded_messages[0].guild_id == testValuesDict["guild_id"]
    assert recorded_messages[0].thread_id == testValuesDict["thread_id"]
    assert recorded_messages[0].user_id == testValuesDict["user_id"]
    assert recorded_messages[0].role == testValuesDict["role"]
    assert recorded_messages[0].message == testValuesDict["message"]


@pytest.mark.asyncio
async def test_usage_table():
    # Record usage to the memory database
    await sql_handler.record_usage(testValuesDict["guild_id"], testValuesDict["thread_id"], testValuesDict["user_id"],
                                   testValuesDict["engine"], testValuesDict["input_tokens"],
                                   testValuesDict["output_tokens"])

    # Retrieve the recorded usages from the memory database
    recorded_usages = sql_handler.get_usage()

    assert recorded_usages is not None
    assert recorded_usages[0].guild_id == testValuesDict["guild_id"]
    assert recorded_usages[0].thread_id == testValuesDict["thread_id"]
    assert recorded_usages[0].user_id == testValuesDict["user_id"]
    assert recorded_usages[0].engine == testValuesDict["engine"]
    assert recorded_usages[0].input_tokens == testValuesDict["input_tokens"]
    assert recorded_usages[0].output_tokens == testValuesDict["output_tokens"]


@pytest.mark.asyncio
async def test_feedback_table():
    # Record feedback to the memory database
    await sql_handler.record_feedback(testValuesDict["guild_id"], testValuesDict["thread_id"],
                                      testValuesDict["user_id"],
                                      testValuesDict["feedback_score"], testValuesDict["reviewer_role_id"])

    # Retrieve the recorded feedback from the memory database
    recorded_feedback = sql_handler.get_feedback()

    assert recorded_feedback is not None
    assert recorded_feedback[0].guild_id == testValuesDict["guild_id"]
    assert recorded_feedback[0].thread_id == testValuesDict["thread_id"]
    assert recorded_feedback[0].user_id == testValuesDict["user_id"]
    assert recorded_feedback[0].feedback_score == testValuesDict["feedback_score"]
    assert recorded_feedback[0].reviewer_role_id == testValuesDict["reviewer_role_id"]
