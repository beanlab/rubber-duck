import csv
import io
import os
import sqlite3
import tempfile
import zipfile

import aiofiles
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

MetricsBase = declarative_base()


def get_timestamp():
    return datetime.now(ZoneInfo('US/Mountain')).isoformat()


class MessagesModel(MetricsBase):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    guild_id = Column(Integer)
    thread_id = Column(Integer)
    user_id = Column(Integer)
    role = Column(String)
    message = Column(String)


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

        self._messages_file = self.get_message()
        self._usage_file = ''
        self._feedback_file = ''

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

    def create_temp_csv(self, messages):
        """Creates a temporary CSV file and returns its file path."""
        if not messages:
            print("⚠️ No messages found, returning None.")
            return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8",
                                         newline='') as temp_csv:
            csv_writer = csv.writer(temp_csv)

            # Extract column names dynamically
            column_names = MessagesModel.__table__.columns.keys()
            csv_writer.writerow(column_names)

            # Write row data
            for message in messages:
                csv_writer.writerow([getattr(message, col) for col in column_names])

            temp_csv_path = temp_csv.name  # Get file path

        print(f"✅ CSV created at {temp_csv_path}")
        return temp_csv_path

    def create_temp_zip(self, files):
        """Creates a temporary ZIP file containing the provided files and returns its file path."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_zip:
            zip_path = temp_zip.name  # Get ZIP file path

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                if file_path and os.path.exists(file_path):
                    zipf.write(file_path, arcname=os.path.basename(file_path))
                else:
                    print(f"⚠️ Warning: File '{file_path}' not found, skipping.")

        print(f"✅ ZIP created at {zip_path}")
        return zip_path