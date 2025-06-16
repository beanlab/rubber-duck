from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Type

from sqlalchemy import Column, Integer, String, BigInteger, text, MetaData, Table
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.inspection import inspect
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.schema import CreateTable

from ..metrics.feedback_manager import FeedbackData
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

    @staticmethod
    def alter_table(
            session: Session,
            model: Type[DeclarativeMeta],
            renamed_columns: dict[str, str] = None
    ) -> None:
        """
            Rebuilds the table with a new schema, migrating data from the old table to the new one.
        """
        try:
            renamed_columns = renamed_columns or {}
            table_name = model.__tablename__
            temp_table_name = f"{table_name}_new"

            duck_logger.info(f"Starting table migration for '{table_name}'")
            duck_logger.info(f"Renamed columns mapping (old → new): {renamed_columns}")

            engine = session.get_bind()
            metadata = MetaData()
            metadata.reflect(bind=engine, only=[table_name])
            old_table = metadata.tables[table_name]

            # Build new table schema
            new_columns = []
            for col in model.__table__.columns:
                new_col = Column(
                    col.name,
                    col.type,
                    primary_key=col.primary_key,
                    nullable=col.nullable,
                    default=col.default,
                    server_default=col.server_default,
                    unique=col.unique,
                    index=col.index
                )
                new_columns.append(new_col)

            # Create the temp table to migrate the data.
            new_table = Table(temp_table_name, MetaData(), *new_columns)
            new_table_sql = str(CreateTable(new_table).compile(engine))
            session.execute(text(new_table_sql))

            # Detect old and new columns
            old_columns = {col.name for col in old_table.columns}
            new_columns_set = {col.name for col in new_table.columns}

            duck_logger.debug(f"Old columns: {old_columns}")
            duck_logger.debug(f"New columns: {new_columns_set}")

            # Map columns changing names if needed.
            column_map = {}
            for new_col in new_columns_set:
                old_col = renamed_columns.get(new_col, new_col)
                if old_col in old_columns:
                    column_map[new_col] = old_col
                else:
                    duck_logger.warning(f"Column '{new_col}' is new and will be NULL for existing rows.")

            if not column_map:
                raise Exception("No columns to migrate — check renamed_columns mapping")

            cols_new = ", ".join(column_map.keys())
            cols_old = ", ".join(column_map.values())

            # Migrate the table data
            copy_stmt = text(f"""
                INSERT INTO {temp_table_name} ({cols_new})
                SELECT {cols_old} FROM {table_name}
            """)
            session.execute(copy_stmt)

            # Replace old table
            session.execute(text(f"DROP TABLE {table_name}"))
            session.execute(text(f"ALTER TABLE {temp_table_name} RENAME TO {table_name}"))
            session.commit()

            duck_logger.info(f"Successfully altered table '{table_name}'. Changes: {renamed_columns}")
        except Exception as e:
            session.rollback()
            duck_logger.exception(f"An error occurred while altering table '{table_name}': {e}")
            raise

    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        try:
            new_message_row = MessagesModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id,
                                            user_id=user_id, role=role, message=message)
            self.session.add(new_message_row)
            self.session.commit()
        except Exception as e:
            duck_logger.exception(f"An error occurred: {e}")

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
            duck_logger.exception(f"An error occurred: {e}")

    async def record_feedback(self, workflow_type: str, guild_id: int, parent_channel_id: int, thread_id: int,
                              user_id: int, reviewer_id: int,
                              feedback_score: int, written_feedback: str):
        try:
            new_feedback_row = FeedbackModel(timestamp=get_timestamp(),
                                             workflow_type=workflow_type,
                                             guild_id=guild_id, parent_channel_id=parent_channel_id,
                                             thread_id=thread_id,
                                             user_id=user_id, reviewer_role_id=reviewer_id,
                                             feedback_score=feedback_score,
                                             written_feedback=written_feedback)
            self.session.add(new_feedback_row)
            self.session.commit()
        except Exception as e:
            duck_logger.exception(f"An error occurred: {e}")

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
