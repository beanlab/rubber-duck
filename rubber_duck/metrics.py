import csv
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


def get_timestamp():
    return datetime.now(ZoneInfo('US/Mountain')).isoformat()


class MetricsHandler:
    def __init__(self, metrics_folder: Path):
        metrics_folder.mkdir(parents=True, exist_ok=True)

        self._messages_file = metrics_folder / 'messages.csv'
        if not self._messages_file.exists():
            self._messages_file.write_text(
                ','.join(['timestamp', 'guild_id', 'thread_id', 'user_id', 'role', 'message']) + '\n')

        self._usage_file = metrics_folder / 'usage.csv'
        if not self._usage_file.exists():
            self._usage_file.write_text(
                ','.join(['timestamp', 'guild_id', 'thread_id', 'user_id', 'engine', 'input_tokens',
                          'output_tokens']) + '\n')

        # Added feedback metrics file
        self._feedback_file = metrics_folder / 'feedback.csv'
        if not self._feedback_file.exists():
            self._feedback_file.write_text(
                ','.join(['timestamp', 'guild_id', 'thread_id', 'user_id', 'reviewer_role_id', 'feedback_score']) + '\n')

    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        with self._messages_file.open('at', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([get_timestamp(), guild_id, thread_id, user_id, role, message])

    async def record_usage(self, guild_id, thread_id, user_id, engine, input_tokens, output_tokens):
        with self._usage_file.open('at', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([get_timestamp(), guild_id, thread_id, user_id, engine, input_tokens, output_tokens])

    # Record the feedback in feedback.csv
    async def record_feedback(self, guild_id: int, thread_id: int, user_id: int, feedback_score):
        try:
            with self._feedback_file.open('at', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([get_timestamp(), guild_id, thread_id, user_id, feedback_score])
        except Exception as e:
            logging.error(f"Failed to record feedback: {e}")

    def get_message(self):
        df = pd.read_csv(self._messages_file)
        return df

        # with self._messages_file.open('rt', newline='') as file:
        #     reader = csv.DictReader(file, fieldnames=["timestamp", "guild_id", "thread_id", "user_id", "role", "message"], )
        #     messages = [row for row in reader]
        # return messages

    def get_usage(self):
        df = pd.read_csv(self._usage_file)
        return df

        # with self._messages_file.open('rt', newline='') as file:
        #     reader = csv.DictReader(file, fieldnames=['timestamp', 'guild_id', 'thread_id', 'user_id', 'engine', 'input_tokens', 'output_tokens'])
        #     messages = [row for row in reader]
        # return messages

    def get_feedback(self):
        df = pd.read_csv(self._feedback_file)
        return df

        # with self._messages_file.open('rt', newline='') as file:
        #     reader = csv.DictReader(file, fieldnames=['timestamp', 'guild_id', 'thread_id', 'user_id', 'reviewer_id', 'feedback_score'])
        #     messages = [row for row in reader]
        # return messages