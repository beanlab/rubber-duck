from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Integer, String, BigInteger
from sqlalchemy.orm import declarative_base, Session

from ..utils.logger import duck_logger

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
    timestamp = Column(String(255))
    guild_id = Column(BigInteger)
    thread_id = Column(BigInteger)
    user_id = Column(BigInteger)
    role = Column(String(255))
    message = Column(String(4096))


@add_iter
class UsageModel(MetricsBase):
    __tablename__ = 'usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(255))
    guild_id = Column(BigInteger)
    parent_channel_id = Column(BigInteger)
    thread_id = Column(BigInteger)
    user_id = Column(BigInteger)
    engine = Column(String(255))
    input_tokens = Column(String(255))
    output_tokens = Column(String(255))
    cached_tokens = Column(String(255))
    reasoning_tokens = Column(String(255))


@add_iter
class FeedbackModel(MetricsBase):
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(255))
    workflow_type = Column(String(255))
    guild_id = Column(BigInteger)
    parent_channel_id = Column(BigInteger)
    thread_id = Column(BigInteger)
    user_id = Column(BigInteger)
    reviewer_role_id = Column(BigInteger)
    feedback_score = Column(BigInteger)
    written_feedback = Column(String(4096))


class SQLMetricsHandler:
    def __init__(self, session: Session):
        MetricsBase.metadata.create_all(session.connection())
        self.session = session

    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        try:
            new_message_row = MessagesModel(timestamp=get_timestamp(),
                                            guild_id=guild_id,
                                            thread_id=thread_id,
                                            user_id=user_id,
                                            role=role,
                                            message=message)
            self.session.add(new_message_row)
            self.session.commit()
        except Exception as e:
            duck_logger.error(f"An error occured: {e}")

    async def record_usage(self, guild_id, parent_channel_id, thread_id, user_id, engine, input_tokens, output_tokens, cached_tokens=None, reasoning_tokens=None):
        try:
            new_usage_row = UsageModel(timestamp=get_timestamp(),
                                       guild_id=guild_id,
                                       parent_channel_id=parent_channel_id,
                                       thread_id=thread_id,
                                       user_id=user_id,
                                       engine=engine,
                                       input_tokens=input_tokens,
                                       output_tokens=output_tokens,
                                       cached_tokens=cached_tokens,
                                       reasoning_tokens=reasoning_tokens)
            self.session.add(new_usage_row)
            self.session.commit()
        except Exception as e:
            duck_logger.error(f"An error occured: {e}")

    async def record_feedback(self, workflow_type: str, guild_id: int, parent_channel_id: int, thread_id: int,
                              user_id: int, reviewer_id: int,
                              feedback_score: int, written_feedback: str):
        try:
            new_feedback_row = FeedbackModel(timestamp=get_timestamp(),
                                             workflow_type=workflow_type,
                                             guild_id=guild_id,
                                             parent_channel_id=parent_channel_id,
                                             thread_id=thread_id,
                                             user_id=user_id,
                                             reviewer_role_id=reviewer_id,
                                             feedback_score=feedback_score,
                                             written_feedback=written_feedback)
            self.session.add(new_feedback_row)
            self.session.commit()
        except Exception as e:
            duck_logger.error(f"An error occured: {e}")

    def sql_model_to_data_list(self, table_model):
        try:
            data = []
            records = iter(self.session.query(table_model).all())
            header = next(records)
            data.append([key for key, _ in header])
            data.append([value for _, value in header])

            for record in records:
                data.append([value for _, value in record])

            return data
        except Exception as e:
            duck_logger.exception(f"An error occurred: {e}")
            raise

    def get_messages(self):
        return self.sql_model_to_data_list(MessagesModel)

    def get_usage(self):
        return self.sql_model_to_data_list(UsageModel)

    def get_feedback(self):
        return self.sql_model_to_data_list(FeedbackModel)
