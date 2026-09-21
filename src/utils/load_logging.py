import logging
import time
from collections import deque
from quest.utils import quest_logger


class _RateLimitFilter(logging.Filter):
    _markers = ("429", "rate limit", "ratelimit", "retry-after", "retry_after")

    def filter(self, record):
        message = record.getMessage().lower()
        return any(marker in message for marker in self._markers)


class _LoadLogBuffer(logging.Handler):
    def __init__(self, max_records=5000):
        super().__init__()
        self._records = deque(maxlen=max_records)
        self.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    def emit(self, record):
        self._records.append(self.format(record))

    def text(self):
        return "\n".join(self._records) + ("\n" if self._records else "")


_buffer = _LoadLogBuffer()
load_logger = logging.getLogger("load")
load_logger.setLevel(logging.INFO)
load_logger.propagate = False
load_logger.addHandler(_buffer)

_discord_logger = logging.getLogger("discord.http")
_discord_logger.setLevel(logging.DEBUG)
_discord_logger.propagate = False
_discord_logger.addFilter(_RateLimitFilter())
_discord_logger.addHandler(_buffer)
quest_logger.addHandler(_buffer)


def workflow_received(workflow_id, message_id, channel_id):
    load_logger.info(
        "workflow_received id=%s message=%s channel=%s",
        workflow_id,
        message_id,
        channel_id,
    )


def workflow_started(workflow_id, started_at):
    load_logger.info(
        "workflow_started id=%s start_delay_ms=%.1f",
        workflow_id,
        (time.monotonic() - started_at) * 1000,
    )


def timed_sync(operation, function, **fields):
    started_at = time.monotonic()
    try:
        result = function()
    except Exception as error:
        load_logger.exception(
            "%s_failed %s error=%s: %s",
            operation,
            _format_fields(fields),
            type(error).__name__,
            error,
        )
        raise

    load_logger.info(
        "%s %s duration_ms=%.1f",
        operation,
        _format_fields(fields),
        (time.monotonic() - started_at) * 1000,
    )
    return result


async def timed(operation, awaitable, result_field=None, **fields):
    started_at = time.monotonic()
    try:
        result = await awaitable
    except Exception:
        load_logger.exception("%s_failed %s", operation, _format_fields(fields))
        raise

    load_logger.info(
        "%s %s duration_ms=%.1f",
        operation,
        _format_fields(fields, result if result_field else None, result_field),
        (time.monotonic() - started_at) * 1000,
    )
    return result


def thread_setup_complete(parent_channel_id, thread_id, started_at):
    load_logger.info(
        "thread_setup_complete channel=%s thread=%s duration_ms=%.1f",
        parent_channel_id,
        thread_id,
        (time.monotonic() - started_at) * 1000,
    )


def get_log_text():
    return _buffer.text()


def _format_fields(fields, result=None, result_field=None):
    if result is not None and result_field:
        fields = {**fields, result_field: result}
    return " ".join(f"{key}={value}" for key, value in fields.items())
