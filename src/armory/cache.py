import asyncio
import functools

from ..utils.logger import duck_logger

_cache: dict = {}


def cache_result(func):
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            key = (func.__name__, *args, tuple(sorted(kwargs.items())))

            if value := _cache.get(key):
                duck_logger.debug(f"Using cached result for {key}")
                return value

            duck_logger.debug(f"Caching result for {key}")
            result = await func(self, *args, **kwargs)
            _cache[key] = result
            return result

        return async_wrapper

    else:
        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            key = (func.__name__, *args, tuple(sorted(kwargs.items())))

            if value := _cache.get(key):
                duck_logger.debug(f"Using cached result for {key}")
                return value

            duck_logger.debug(f"Caching result for {key}")
            result = func(self, *args, **kwargs)
            _cache[key] = result
            return result

        return sync_wrapper
