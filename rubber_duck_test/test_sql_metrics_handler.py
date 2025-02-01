import pytest, asyncio

from rubber_duck.connection import DatabaseConnection
from rubber_duck.sql_metrics import SQLMetricsHandler

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

testValuesDict = {
    "guild_id": 1234,
    "thread_id": 5678,
    "user_id": 123456789,
    "role": "test-role",
    "message": "test-message",
    "engine": "test-engine",
    "input_tokens":"test-input-token",
    "output_tokens": "test-output-token",
    "reviewer_role_id": 987654,
    "feedback_score": 4
}

class MessagesModel(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    role = Column(String)
    message = Column(String)

class UsageModel(Base):
    __tablename__ = 'usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    engine = Column(String)
    input_tokens = Column(String)
    output_tokens = Column(String)


class FeedbackModel(Base):
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    reviewer_role_id = Column(Integer)
    feedback_score = Column(Integer)

@pytest.mark.asyncio
async def test_sql_metrics_handler():
    connection = DatabaseConnection(Base, 'sqlite:///:memory:')
    sql_handler = SQLMetricsHandler(connection)

    # Record message to the memory database
    await sql_handler.record_message(testValuesDict["guild_id"], testValuesDict["thread_id"],testValuesDict["user_id"],testValuesDict["role"], testValuesDict["message"])

    # Retrieve the recorded messages from the memory database
    recorded_messages = sql_handler.get_message()

    assert recorded_messages is not None
    assert recorded_messages[0].guild_id == testValuesDict["guild_id"]
    assert recorded_messages[0].thread_id == testValuesDict["thread_id"]
    assert recorded_messages[0].user_id == testValuesDict["user_id"]
    assert recorded_messages[0].role == testValuesDict["role"]
    assert recorded_messages[0].message == testValuesDict["message"]


    # Record usage to the memory database
    await sql_handler.record_usage(testValuesDict["guild_id"], testValuesDict["thread_id"], testValuesDict["user_id"],
                                     testValuesDict["engine"], testValuesDict["input_tokens"], testValuesDict["output_tokens"])

    # Retrieve the recorded usages from the memory database
    recorded_usages = sql_handler.get_usage()

    assert recorded_usages is not None
    assert recorded_usages[0].guild_id == testValuesDict["guild_id"]
    assert recorded_usages[0].thread_id == testValuesDict["thread_id"]
    assert recorded_usages[0].user_id == testValuesDict["user_id"]
    assert recorded_usages[0].engine == testValuesDict["engine"]
    assert recorded_usages[0].input_tokens == testValuesDict["input_tokens"]
    assert recorded_usages[0].output_tokens == testValuesDict["output_tokens"]

    # Record feedback to the memory database
    await sql_handler.record_feedback(testValuesDict["guild_id"], testValuesDict["thread_id"], testValuesDict["user_id"],
                                   testValuesDict["feedback_score"], testValuesDict["reviewer_role_id"])

    # Retrieve the recorded feedback from the memory database
    recorded_feedback = sql_handler.get_feedback()

    assert recorded_feedback is not None
    assert recorded_feedback[0].guild_id == testValuesDict["guild_id"]
    assert recorded_feedback[0].thread_id == testValuesDict["thread_id"]
    assert recorded_feedback[0].user_id == testValuesDict["user_id"]
    assert recorded_feedback[0].feedback_score == testValuesDict["feedback_score"]
    assert recorded_feedback[0].reviewer_role_id == testValuesDict["reviewer_role_id"]
