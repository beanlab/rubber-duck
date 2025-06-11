from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Type

from sqlalchemy import Column, Integer, String, BigInteger, text, MetaData, Table
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.inspection import inspect
from sqlalchemy.ext.declarative import DeclarativeMeta

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
    def __init__(self, session: Session, renamed_columns: dict):
        MetricsBase.metadata.create_all(session.connection())
        self.session = session
        self.renamed_columns = renamed_columns
        self.migrate_or_rebuild_table(session, MessagesModel)
        self.migrate_or_rebuild_table(session, UsageModel)
        self.migrate_or_rebuild_table(session, FeedbackModel)

    def migrate_or_rebuild_table(self, session, model: Type[DeclarativeMeta])->None:
        """
        When given a model, this function will check if the tables needs to be migrated or rebuilt.
        """
        table_name = model.__tablename__
        rename_map = self.renamed_columns.get(table_name, {})
        
        # Return None if no renamed columns are specified
        if not self.renamed_columns or not rename_map:
            return None
            
        logger = duck_logger

        # Step 1: Get current DB column names/types
        try:
            db_columns = session.execute(text(f"PRAGMA table_info({table_name});")).fetchall()
            db_column_names = {col[1]: col for col in db_columns}
            db_column_set = set(db_column_names.keys())
        except Exception:
            db_column_names = {}
            db_column_set = set()

        # Step 2: Model columns
        model_column_names = [c.name for c in model.__table__.columns]
        model_column_set = set(model_column_names)

        # Step 3: Detect missing and incompatible columns
        missing_columns = model_column_set - db_column_set
        incompatible_columns = []

        for col in model_column_names:
            if col in db_column_names:
                db_type = db_column_names[col][2].upper()
                model_type = str(model.__table__.columns[col].type).upper()
                if db_type != model_type:
                    incompatible_columns.append((col, db_type, model_type))

        # Step 4: Safe add missing columns
        if missing_columns and not incompatible_columns:
            for col in missing_columns:
                col_type = str(model.__table__.columns[col].type).upper()
                try:
                    session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type}"))
                    logger.info(f"Added column '{col}' to '{table_name}'")
                except Exception as e:
                    logger.exception(f"Error adding column '{col}': {e}")
            session.commit()
            return

        # Step 5: Rebuild required
        logger.warning(f"Rebuilding table '{table_name}' to match model schema.")

        metadata = MetaData()
        temp_table_name = f"{table_name}_temp"
        new_table = Table(temp_table_name, metadata, *model.__table__.columns)
        new_table.create(bind=session.get_bind())

        # Step 6: Build shared columns (handle renames)
        shared_columns = []
        for model_col in model_column_names:
            # Try to find source in DB
            db_col = next((old for old, new in rename_map.items() if new == model_col), model_col)
            if db_col in db_column_names:
                shared_columns.append((model_col, db_col))

        # Step 7: Copy data from old table to temp table
        if shared_columns:
            target_cols = ", ".join(col for col, _ in shared_columns)
            source_cols = ", ".join(src for _, src in shared_columns)
            insert_sql = f"INSERT INTO {temp_table_name} ({target_cols}) SELECT {source_cols} FROM {table_name}"
            session.execute(text(insert_sql))

        # Step 8: Replace old table
        session.execute(text(f"DROP TABLE {table_name}"))
        session.execute(text(f"ALTER TABLE {temp_table_name} RENAME TO {table_name}"))
        session.commit()
        logger.info(f"Table '{table_name}' successfully rebuilt.")

    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        try:
            new_message_row = MessagesModel(timestamp=get_timestamp(), guild_id=guild_id, thread_id=thread_id,
                                            user_id=user_id, role=role, message=message)
            self.session.add(new_message_row)
            self.session.commit()
        except Exception as e:
            duck_logger.error(f"An error occurred: {e}")

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
            duck_logger.error(f"An error occurred: {e}")

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
            duck_logger.error(f"An error occurred: {e}")

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

    @staticmethod
    def add_column_if_not_exists(session, table_name: str, column_name: str, column_type: str, default: str = None):
        """Function to add a column to a table if it does not already exist."""
        # Check if column exists using SQLAlchemy's inspect
        inspector = inspect(session.get_bind())
        columns = [col['name'] for col in inspector.get_columns(table_name)]

        if column_name not in columns:
            # For SQLite, we need to handle DEFAULT values differently
            ddl = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            if default is not None:
                # If default is already quoted, use it as is
                if default.startswith("'") or default.startswith('"'):
                    ddl += f" DEFAULT {default}"
                else:
                    # For numeric values, use as is
                    ddl += f" DEFAULT {default}"
            try:
                session.execute(text(ddl))
                session.commit()
                duck_logger.info(f"Added column '{column_name}' to '{table_name}'")
            except Exception as e:
                duck_logger.exception(f"Error adding column '{column_name}' to '{table_name}': {e}")
                raise DatabaseError(f"Failed to add column '{column_name}' to '{table_name}': {e}")

    def get_messages(self):
        return self.sql_model_to_data_list(MessagesModel)

    def get_usage(self):
        return self.sql_model_to_data_list(UsageModel)

    def get_feedback(self):
        return self.sql_model_to_data_list(FeedbackModel)
