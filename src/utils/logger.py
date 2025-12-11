import asyncio
import logging
import re
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler, QueueHandler
from queue import Queue

from quest.utils import quest_logger

from ..utils.config_types import AdminSettings

thread_id_context = ContextVar("thread_id", default='-')


class ThreadIdFieldFilter(logging.Filter):
    def filter(self, record):
        record.thread_id = thread_id_context.get()
        return True


formatter = logging.Formatter(
    fmt='%(asctime)s %(levelname).4s <#%(thread_id)s> %(name)s - %(task)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set up loggers
duck_logger = logging.getLogger("duck")
duck_logger.setLevel(logging.DEBUG)
duck_logger.addFilter(ThreadIdFieldFilter())
quest_logger.setLevel(logging.INFO)
quest_logger.addFilter(ThreadIdFieldFilter())


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
ERROR_RE = re.compile(
    r"""
    ^\S+\s+\S+\s+ERRO\s+
    <#(?P<thread_id>\d+)>\s+
    (?P<prefix>[\w\-]+)\s*-\s*
    (?P<channel_id>\d+)-(?P<message_id>\d+)\.[^-\s]+\s*-\s*
    (?P<error_msg>.*)
    """,
    re.VERBOSE,
)


def truncate_message(msg: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate message to fit Discord limits, keeping the bottom of the traceback"""
    if len(msg) > max_length:
        return "... (truncated) ...\n" + msg[-max_length:]
    return msg


def format_error_message(raw: str) -> str:
    """
    Parse and format an error message for Discord readability
    Expected input format:

    yyyy-mm-dd hh:mm:ss ERRO <#thread_id> duck - duck-<channel_id>-<msg_id>.main - this is a sample error message
    """
    m = ERROR_RE.match(raw)
    if not m:
        # if not matched, use simple code fence
        return f"```\n{raw}\n```"

    thread_id = m.group("thread_id")
    channel_id = m.group("channel_id")
    message_id = m.group("message_id")
    error_msg = m.group("error_msg")

    # truncate only the error message, keeping the end of the message and not the beginning
    error_msg = truncate_message(error_msg)

    formatted = (
        f"**Error in thread:** <#{thread_id}>\n"
        f"**Channel ID:** `{channel_id}`\n"
        f"**Message ID:** `{message_id}`\n\n"
        f"Traceback:\n```\n{error_msg}\n```"
    )
    return formatted


async def log_queue_watcher(send_message, channel_id, log_queue: Queue):
    loop = asyncio.get_running_loop()

    def _blocking_get():
        return log_queue.get()  # blocking call in thread

    while True:
        record = await loop.run_in_executor(None, _blocking_get)
        message = record.getMessage()
        formatted_message = format_error_message(message)

        try:
            await send_message(channel_id, formatted_message)
        except Exception as e:
            duck_logger.debug(f"Failed to send log message to Discord: {e}")
            duck_logger.debug(message)
