import asyncio
from datetime import datetime, timedelta

from .protocols import ToolCache
from .logger import duck_logger


class CacheCleaner:
    """A class that runs cache cleanup once daily"""

    def __init__(self, tool_caches: list[ToolCache], cleanup_hour: int, cleanup_minute: int):
        self._tool_caches = tool_caches
        self._cleanup_hour = cleanup_hour
        self._cleanup_minute = cleanup_minute

    async def start(self):
        duck_logger.info(
            f"Starting cache cleanup scheduler at {self._cleanup_hour:02d}:{self._cleanup_minute:02d} (local time)"
        )

        while True:
            now = datetime.now()
            next_run = now.replace(hour=self._cleanup_hour, minute=self._cleanup_minute, second=0, microsecond=0)
            if now >= next_run:
                next_run = next_run + timedelta(days=1)

            sleep_seconds = (next_run - now).total_seconds()
            duck_logger.debug(f"Next cache cleanup scheduled for {next_run}")
            await asyncio.sleep(sleep_seconds)

            for i, tool_cache in enumerate(self._tool_caches):
                try:
                    await asyncio.to_thread(tool_cache.cleanup)
                except Exception:
                    duck_logger.exception(f"Cache cleanup failed for tool cache index {i}")
