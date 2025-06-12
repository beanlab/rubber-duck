import logging
import asyncio
from logging.handlers import TimedRotatingFileHandler, QueueHandler
from queue import Queue
from quest.utils import quest_logger
from ..utils.config_types import AdminSettings

formatter = logging.Formatter(
    fmt='%(asctime)s %(levelname).4s %(name)s - %(task)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Set up loggers
duck_logger = logging.getLogger("duck")
duck_logger.setLevel(logging.DEBUG)
duck_logger.addHandler(console_handler)

quest_logger.setLevel(logging.DEBUG)
quest_logger.addHandler(console_handler)


def add_file_handler(file_path: str):
    """Add a file handler to the duck logger."""
    file_handler = TimedRotatingFileHandler(
        filename=file_path,
        when='midnight',
        interval=1,
        backupCount=2,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    duck_logger.addHandler(file_handler)
    quest_logger.addHandler(file_handler)

# Function to start reporting error logs to Discord
def filter_logs(send_message, config: AdminSettings):
    """Filter logs to send them to Discord."""
    log_queue = Queue()
    level_name = config["log_level"].upper()
    log_level = getattr(logging, level_name, logging.ERROR)

    q_handler = QueueHandler(log_queue)
    q_handler.setLevel(log_level)
    q_handler.setFormatter(formatter)

    duck_logger.addHandler(q_handler)
    quest_logger.addHandler(q_handler)

    asyncio.create_task(log_queue_watcher(send_message, config['admin_channel_id'], log_queue))


async def log_queue_watcher(send_message, channel_id, log_queue: Queue):
    loop = asyncio.get_running_loop()

    def _blocking_get():
        return log_queue.get()  # blocking call in thread

    while True:
        record = await loop.run_in_executor(None, _blocking_get)
        message = record.getMessage()

        try:
            await send_message(channel_id, f"[{record.levelname}] {message}")
        except Exception as e:
            print(f"Failed to send log message to Discord: {e}")
