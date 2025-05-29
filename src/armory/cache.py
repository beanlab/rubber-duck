import functools

from ..utils.logger import duck_logger

_cache: dict = {}


def cache_result(func):

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        key = (func.__name__, *args, tuple(sorted(kwargs.items())))
        if value := _cache.get(key):
            duck_logger.debug(f"Using cached result for {key}")
            return value
        duck_logger.debug(f"Caching result for {key}")
        result = func(self, *args, **kwargs)
        _cache[key] = result
        return result

    return wrapper
