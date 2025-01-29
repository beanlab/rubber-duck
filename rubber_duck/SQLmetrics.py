import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from quest import step
from sqlalchemy import Column, Integer, String, DATETIME
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, sessionmaker

from connection import DatabaseConnection

Base = declarative_base()

def get_timestamp():
    return datetime.now(ZoneInfo('US/Mountain')).isoformat()

class MessagesModel(Base):
    __tablename__ = 'messages'

    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    role = Column(String)
    message = Column(String)


class UsageModel(Base):
    __tablename__ = 'usage'

    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    engine = Column(String)
    input_tokens = Column(String)
    output_tokens = Column(String)


class FeedbackModel(Base):
    __tablename__ = 'usage'

    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    reviewer_role_id = Column(Integer)
    feedback_score = Column(Integer)



class SQLMetricsHandler:
    def __init__(self):
        self.db = DatabaseConnection(Base)
        self.session = self.db.get_session()

    @step
    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        try:
            newMessageRow = MessagesModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id, user_id=user_id,
                                       role=role, message=message)
            self.session.add(newMessageRow)
            self.session.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    @step
    async def record_usage(self, guild_id, thread_id, user_id, engine, input_tokens, output_tokens):
        try:
            newUsageRow = UsageModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id, user_id=user_id,
                                  engine=engine, input_tokens=input_tokens, output_tokens=output_tokens)
            self.session.add(newUsageRow)
            self.session.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    @step
    async def record_feedback(self, guild_id: int, thread_id: int, user_id: int, feedback_score: int, reviewer_id: int):
        try:
            newFeedbackRow = FeedbackModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id, user_id=user_id,
                                           reviewer_role_id=reviewer_id, feedback_score=feedback_score)
            self.session.add(newFeedbackRow)
            self.session.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    def get_message(self):
        try:
            messagesTable = """ SELECT * FROM messages """
            return self.cursor.execute(messagesTable)
        except sqlite3.Error as e:
            print(f"An error occured: {e}")


    def get_usage(self):
        try:
            usageTable = """ SELECT * FROM usage """
            return self.cursor.execute(usageTable)
        except sqlite3.Error as e:
            print(f"An error occured: {e}")


    def get_feedback(self):
        try:
            feedbackTable = """ SELECT * FROM feedback """
            return self.cursor.execute(feedbackTable)
        except sqlite3.Error as e:
            print(f"An error occured: {e}")
