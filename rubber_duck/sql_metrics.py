import sqlite3

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base, Session

MetricsBase = declarative_base()


def get_timestamp():
    return datetime.now(ZoneInfo('US/Mountain')).isoformat()

def add_iter(cls):
    def __iter__(self):
        for key in self.__table__.columns.keys():
            yield key, getattr(self, key)
    cls.__iter__ = __iter__
    return cls

@add_iter
class MessagesModel(MetricsBase):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    role = Column(String)
    message = Column(String)


@add_iter
class UsageModel(MetricsBase):
    __tablename__ = 'usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    engine = Column(String)
    input_tokens = Column(String)
    output_tokens = Column(String)


@add_iter
class FeedbackModel(MetricsBase):
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    workflow_type = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    reviewer_role_id = Column(Integer)
    feedback_score = Column(Integer)


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

    async def record_feedback(self, workflow_type: str, guild_id: int, thread_id: int, user_id: int, reviewer_id: int, feedback_score: int):
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

    def reformat_model(self, table_model):
        try:
            model_list = self.session.query(table_model).all()
            data = []
            for model in model_list:
                values = [value for key, value in iter(model)]

                # If data is empty, add the keys as the first row
                if not data:
                    keys = [key for key, _ in iter(model)]
                    data.append(keys)

                # Add the values
                data.append(values)
            return data
        except sqlite3.Error as e:
            print(f"An error occured: {e}")

    def get_messages(self):
        return self.reformat_model(MessagesModel)

    def get_usage(self):
        return self.reformat_model(UsageModel)

    def get_feedback(self):
        return self.reformat_model(FeedbackModel)
