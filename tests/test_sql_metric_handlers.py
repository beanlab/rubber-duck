import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.sql_metrics import SQLMetricsHandler


def _new_handler():
    return SQLMetricsHandler(Session(create_engine("sqlite:///:memory:")))


def test_messages_table():
    handler = _new_handler()
    for conversation_id in (4444, 5555):
        asyncio.run(handler.record_message(
            guild_id=1234,
            conversation_id=conversation_id,
            user_id=123456789,
            type_="assistant",
            output={"message": "test-message"},
        ))
    messages = handler.get_messages()
    assert messages[0] == [
        "id", "timestamp", "guild_id", "conversation_id", "user_id", "type", "output"
    ]
    assert messages[1][2:] == [1234, 4444, 123456789, "assistant", {"message": "test-message"}]
    assert messages[2][3] == 5555


def test_usage_table():
    handler = _new_handler()
    asyncio.run(handler.record_usage(
        guild_id=1234,
        parent_channel_id=2222,
        conversation_id=4444,
        user_id=123456789,
        engine="test-engine",
        input_tokens="10",
        output_tokens="20",
    ))
    usage = handler.get_usage()
    assert usage[0] == [
        "id", "timestamp", "guild_id", "parent_channel_id", "conversation_id",
        "user_id", "engine", "input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens",
    ]
    assert usage[1][2:7] == [1234, 2222, 4444, 123456789, "test-engine"]


def test_feedback_table():
    handler = _new_handler()
    asyncio.run(handler.record_feedback(
        workflow_type="test-workflow",
        guild_id=1234,
        parent_channel_id=2222,
        conversation_id=4444,
        user_id=123456789,
        reviewer_id=987654,
        feedback_score=4,
        written_feedback="nice work",
    ))
    feedback = handler.get_feedback()
    assert feedback[0] == [
        "id", "timestamp", "workflow_type", "guild_id", "parent_channel_id",
        "conversation_id", "user_id", "reviewer_role_id", "feedback_score", "written_feedback",
    ]
    assert feedback[1][3:] == [1234, 2222, 4444, 123456789, 987654, 4, "nice work"]
