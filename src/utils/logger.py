import asyncio
import logging
import traceback
from logging.handlers import TimedRotatingFileHandler, QueueHandler
from queue import Queue

from quest.utils import quest_logger

from ..utils.config_types import AdminSettings

formatter = logging.Formatter(
    fmt='%(asctime)s %(levelname).4s %(name)s - %(task)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set up loggers
duck_logger = logging.getLogger("duck")
duck_logger.setLevel(logging.DEBUG)
quest_logger.setLevel(logging.INFO)


def add_console_handler():
    """Add a console handler to the duck logger."""
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    duck_logger.addHandler(console_handler)
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
    level_name = config.get('log_level', 'WARN').upper()
    log_level = getattr(logging, level_name)

    q_handler = QueueHandler(log_queue)
    q_handler.setLevel(log_level)
    q_handler.setFormatter(formatter)

    duck_logger.addHandler(q_handler)
    quest_logger.addHandler(q_handler)

    asyncio.create_task(log_queue_watcher(send_message, config['admin_channel_id'], log_queue))

MAX_FRAMES = 10
MAX_MESSAGE_LENGTH = 1990

def format_exception_md(record) -> str:
    """
    Format an exception record into Discord Markdown.
    Preserves the exact order, indentation, and content of the original traceback,
    skipping any lines that are only carets (^), and adds a header with the exception line.
    """
    try:
        exc_info = record.exc_info
        if exc_info:
            tb_lines = traceback.format_exception(*exc_info)
        else:
            tb_lines = record.getMessage().splitlines()
    except Exception:
        tb_lines = record.getMessage().splitlines()

    # Filter out lines that are only carets
    filtered_lines = [line for line in tb_lines if set(line.strip()) != {'^'}]

    # Grab the last line for the header (exception message)
    exc_line = filtered_lines[-1].strip() if filtered_lines else "Unknown Exception"

    # Build the final Markdown message with header
    markdown_message = f"# ❌ Exception:\n`{exc_line}`\n# 📂 Traceback:\n(most recent call last)\n```python\n" + "\n".join(filtered_lines) + "\n```"

    return markdown_message

def truncate_message(msg: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate message to fit Discord limits, keeping the most recent content (bottom of traceback)."""
    if len(msg) > max_length:
        return "... (truncated) ...\n" + msg[-max_length:]
    return msg


async def log_queue_watcher(send_message, channel_id, log_queue: Queue):
    """
    Watches the logging queue and sends formatted error messages to Discord.
    """
    loop = asyncio.get_running_loop()

    def _blocking_get():
        return log_queue.get()

    while True:
        record = await loop.run_in_executor(None, _blocking_get)

        if record.levelname not in ("ERROR", "CRITICAL"):
            continue

        discord_message = format_exception_md(record)
        discord_message = truncate_message(discord_message)

        try:
            await send_message(channel_id, discord_message)
        except Exception as e:
            duck_logger.debug(f"Failed to send log message to Discord: {e}")
            duck_logger.debug(f"[{record.levelname}] {record.getMessage()}")


