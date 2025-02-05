import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from quest import step
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from rubber_duck.connection import DatabaseConnection

Base = declarative_base()

def get_timestamp():
    return datetime.now(ZoneInfo('US/Mountain')).isoformat()


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


class SQLMetricsHandler:
    def __init__(self, connection=DatabaseConnection(Base)):
        self.connection = connection
        self.session = self.connection.get_session()

    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        try:
            new_message_row = MessagesModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id,
                                          user_id=user_id, role=role, message=message)
            self.session.add(new_message_row)
            self.session.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    async def record_usage(self, guild_id, thread_id, user_id, engine, input_tokens, output_tokens):
        try:
            new_usage_row = UsageModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id, user_id=user_id,
                                     engine=engine, input_tokens=input_tokens, output_tokens=output_tokens)
            self.session.add(new_usage_row)
            self.session.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    async def record_feedback(self, guild_id: int, thread_id: int, user_id: int, feedback_score: int, reviewer_id: int):
        try:
            new_feedback_row = FeedbackModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id,
                                           user_id=user_id, reviewer_role_id=reviewer_id, feedback_score=feedback_score)
            self.session.add(new_feedback_row)
            self.session.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    def get_message(self):
        try:
            return self.session.query(MessagesModel).all()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    def get_usage(self):
        try:
            return self.session.query(UsageModel).all()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    def get_feedback(self):
        try:
            return self.session.query(FeedbackModel).all()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")
