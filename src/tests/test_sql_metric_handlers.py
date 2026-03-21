import asyncio
import sys
import types
import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
quest_mod = types.ModuleType("quest")
quest_utils_mod = types.ModuleType("quest.utils")
quest_utils_mod.quest_logger = logging.getLogger("quest")
quest_mod.utils = quest_utils_mod
sys.modules.setdefault("quest", quest_mod)
sys.modules.setdefault("quest.utils", quest_utils_mod)

from src.storage.sql_metrics import SQLMetricsHandler


def _new_handler() -> SQLMetricsHandler:
    engine = create_engine("sqlite:///:memory:")
    session = sessionmaker(bind=engine)()
    return SQLMetricsHandler(session)


def test_messages_table():
    handler = _new_handler()
    asyncio.run(
        handler.record_message(
            guild_id=1234,
            thread_id=5678,
            user_id=123456789,
            type_="assistant",
            output={"message": "test-message"},
        )
    )
    recorded_messages = handler.get_messages()
    assert recorded_messages[0] == ["id", "timestamp", "guild_id", "thread_id", "user_id", "type", "output"]
    assert recorded_messages[1][2] == 1234
    assert recorded_messages[1][3] == 5678
    assert recorded_messages[1][4] == 123456789
    assert recorded_messages[1][5] == "assistant"
    assert recorded_messages[1][6] == {"message": "test-message"}


def test_usage_table():
    handler = _new_handler()
    asyncio.run(
        handler.record_usage(
            guild_id=1234,
            parent_channel_id=2222,
            thread_id=5678,
            user_id=123456789,
            engine="test-engine",
            input_tokens="10",
            output_tokens="20",
        )
    )
    recorded_usage = handler.get_usage()
    assert recorded_usage[0] == [
        "id",
        "timestamp",
        "guild_id",
        "parent_channel_id",
        "thread_id",
        "user_id",
        "engine",
        "input_tokens",
        "output_tokens",
        "cached_tokens",
        "reasoning_tokens",
    ]
    assert recorded_usage[1][2] == 1234
    assert recorded_usage[1][3] == 2222
    assert recorded_usage[1][4] == 5678
    assert recorded_usage[1][5] == 123456789
    assert recorded_usage[1][6] == "test-engine"


def test_feedback_table():
    handler = _new_handler()
    asyncio.run(
        handler.record_feedback(
            workflow_type="test-workflow",
            guild_id=1234,
            parent_channel_id=2222,
            thread_id=5678,
            user_id=123456789,
            reviewer_id=987654,
            feedback_score=4,
            written_feedback="nice work",
        )
    )
    recorded_feedback = handler.get_feedback()
    assert recorded_feedback[0] == [
        "id",
        "timestamp",
        "workflow_type",
        "guild_id",
        "parent_channel_id",
        "thread_id",
        "user_id",
        "reviewer_role_id",
        "feedback_score",
        "written_feedback",
    ]
    assert recorded_feedback[1][3] == 1234
    assert recorded_feedback[1][4] == 2222
    assert recorded_feedback[1][5] == 5678
    assert recorded_feedback[1][6] == 123456789
    assert recorded_feedback[1][7] == 987654
    assert recorded_feedback[1][8] == 4
