import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .config_types import RetryProtocol

T = TypeVar("T")


def retry_delay_seconds(retry_protocol: RetryProtocol, attempt: int) -> int:
    base_delay = max(0, int(retry_protocol.get("delay", 0)))
    backoff = max(1, int(retry_protocol.get("backoff", 1)))
    return base_delay * (backoff ** attempt)


def is_retryable_discord_server_error(error: Exception) -> bool:
    return (
        error.__class__.__name__ == "DiscordServerError" and
        getattr(error, "status", None) == 503
    )


async def retry_async(
        operation: Callable[[], Awaitable[T]],
        retry_protocol: RetryProtocol,
        should_retry: Callable[[Exception], bool],
        on_retry: Callable[[Exception, int, int], Awaitable[None]] | None = None,
        on_exhausted: Callable[[Exception, int], Awaitable[None]] | None = None,
) -> T:
    max_retries = max(0, int(retry_protocol.get("max_retries", 0)))

    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except Exception as error:
            if should_retry(error) and attempt == max_retries:
                if on_exhausted:
                    await on_exhausted(error, attempt)
                raise

            should_retry_error = (
                attempt < max_retries and
                should_retry(error)
            )
            if not should_retry_error:
                raise

            delay_seconds = retry_delay_seconds(retry_protocol, attempt)
            if on_retry:
                await on_retry(error, attempt, delay_seconds)
            await asyncio.sleep(delay_seconds)

    raise RuntimeError("Retry loop exited unexpectedly.")
