import asyncio

from src.testing.prompt_evaluation.concurrency import map_concurrently


def test_map_concurrently_respects_limit_and_order() -> None:
    active = 0
    maximum = 0

    async def worker(value: int) -> int:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return value * 2

    results = asyncio.run(map_concurrently([1, 2, 3, 4], worker, limit=2))

    assert results == [2, 4, 6, 8]
    assert maximum == 2
