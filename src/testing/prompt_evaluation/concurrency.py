"""Bounded concurrency for prompt evaluation cases."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar


Input = TypeVar("Input")
Output = TypeVar("Output")


async def map_concurrently(
    items: Sequence[Input],
    worker: Callable[[Input], Awaitable[Output]],
    *,
    limit: int,
) -> list[Output]:
    """Run independent cases concurrently while preserving input order."""
    if limit < 1:
        raise ValueError("Concurrency limit must be at least 1")

    semaphore = asyncio.Semaphore(limit)

    async def run(item: Input) -> Output:
        async with semaphore:
            return await worker(item)

    return list(await asyncio.gather(*(run(item) for item in items)))
