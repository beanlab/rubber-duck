import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Integer, String, create_engine, BigInteger
from sqlalchemy.orm import declarative_base, sessionmaker, Session

MetricsBase = declarative_base()


def get_timestamp():
    return datetime.now(ZoneInfo('US/Mountain')).isoformat()


class MessagesModel(MetricsBase):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(255))
    guild_id = Column(BigInteger)
    thread_id = Column(BigInteger)
    user_id = Column(BigInteger)
    role = Column(String(255))
    message = Column(String(4096))


class UsageModel(MetricsBase):
    __tablename__ = 'usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(255))
    guild_id = Column(BigInteger)
    thread_id = Column(BigInteger)
    user_id = Column(BigInteger)
    engine = Column(String(255))
    input_tokens = Column(String(255))
    output_tokens = Column(String(255))


class FeedbackModel(MetricsBase):
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(255))
    workflow_type = Column(String(255))
    guild_id = Column(BigInteger)
    thread_id = Column(BigInteger)
    user_id = Column(BigInteger)
    reviewer_role_id = Column(BigInteger)
    feedback_score = Column(BigInteger)




class SQLMetricsHandler:
    def __init__(self, session: Session):
        MetricsBase.metadata.create_all(session.connection())
        self.session = session

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
            new_usage_row = UsageModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id,
                                       user_id=user_id,
                                       engine=engine, input_tokens=input_tokens, output_tokens=output_tokens)
            self.session.add(new_usage_row)
            self.session.commit()
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    async def record_feedback(self, workflow_type: str, guild_id: int, thread_id: int, user_id: int, reviewer_id: int,
                              feedback_score: int):
        try:
            new_feedback_row = FeedbackModel(timestamp=get_timestamp(),
                                             workflow_type=workflow_type,
                                             guild_id=guild_id, thread_id=thread_id,
                                             user_id=user_id, reviewer_role_id=reviewer_id,
                                             feedback_score=feedback_score)
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
