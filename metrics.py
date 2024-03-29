import csv
from pathlib import Path
import datetime


def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


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
                ','.join(['timestamp', 'guild_id', 'thread_id', 'user_id', 'engine', 'input_tokens', 'output_tokens']) + '\n')

    async def record_message(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str):
        with self._messages_file.open('at', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([get_timestamp(), guild_id, thread_id, user_id, role, message])

    async def record_usage(self, guild_id, thread_id, user_id, engine, input_tokens, output_tokens):
        with self._usage_file.open('at', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([get_timestamp(), guild_id, thread_id, user_id, engine, input_tokens, output_tokens])
