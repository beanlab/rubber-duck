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


ERROR_RE = re.compile(
    r"""
    ^(?:\[ERROR\]\s+)?
    \S+\s+\S+
    \s+ERRO\s+
    <\#(?P<thread_id>\d+|-)>\s+
    (?P<prefix>[\w\-]+)\s*-\s*
    (?P<extra>[\w\-]+)\s*-\s*
    (?P<channel_id>\d+)-(?P<message_id>\d+)\.[^\s]+\s*-\s*
    (?P<error_msg>[^\n]*)
    (?:\n(?P<tracebacks>Traceback[\s\S]*))?
    $
    """,
    re.VERBOSE | re.DOTALL
)

CHAIN_MARKER = "\nDuring handling of the above exception, another exception occurred:\n"


def split_chained_tracebacks(tracebacks: str) -> list[str]:
    """
    Split a traceback blob into individual chained traceback blocks.
    """
    return tracebacks.strip().split(CHAIN_MARKER)


def extract_final_exception(block: str) -> str:
    """
    Extract the final exception line from a traceback block.
    """
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    return lines[-1]


def format_error_message(raw: str) -> str:
    """
    Parse and format an error message for Discord readability.
    """
    m = ERROR_RE.match(raw)
    if not m:
        duck_logger.debug(f"unrecognized error message format: {raw}")
        return raw

    try:
        thread_id = m.group("thread_id")
        error_msg = m.group("error_msg")
        tracebacks = m.group("tracebacks")
    except IndexError:
        duck_logger.debug(f"failed to parse groups: {m.groups()}")
        return raw

    parts: list[str] = [
        f"## Error in thread: <#{thread_id}>",
        "",
        error_msg,
        ""
    ]

    if not tracebacks:
        return "\n".join(parts)

    chained_blocks = split_chained_tracebacks(tracebacks)

    for i, block in enumerate(chained_blocks):
        final_exc = extract_final_exception(block)

        parts.append("```")
        parts.append(block.strip())
        parts.append("```")
        parts.append(f"**CAUSE --** {final_exc}")

        if i < len(chained_blocks) - 1:
            parts.append("\n---\n")
            parts.append("During handling of the above exception, another exception occurred:")
            parts.append("")

    return "\n".join(parts)


async def log_queue_watcher(send_message, channel_id, log_queue: Queue):
    loop = asyncio.get_running_loop()

    def _blocking_get():
        return log_queue.get()

    while True:
        record = await loop.run_in_executor(None, _blocking_get)
        message = record.getMessage()
        formatted_message = format_error_message(message)
        try:
            await send_message(channel_id, formatted_message)
        except Exception as e:
            duck_logger.debug(f"Failed to send log message to Discord: {e}")
            duck_logger.debug(message)
