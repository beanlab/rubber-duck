import functools
import io

from ..utils.logger import duck_logger


class Cache:
    def __init__(self):
        self.cache = {}

    @staticmethod
    def cache_key(*args, **kwargs):
        key_parts = [str(arg) for arg in args]
        key_parts += [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return "_".join(key_parts)

    def get(self, key):
        return self.cache.get(key)

    def put(self, key, value):
        self.cache[key] = value


def cache_result(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        key = Cache.cache_key(method.__name__, *args, **kwargs)
        if value := self._cache.get(key):
            duck_logger.debug(f"Using cached result for {method.__name__} with key={key}")
            if isinstance(value, tuple) and any(isinstance(v, io.BytesIO) for v in value):
                for v in value:
                    if isinstance(v, io.BytesIO):
                        v.seek(0)
            return value

        duck_logger.debug(f"Caching result for {method.__name__} with key={key}")
        result = method(self, *args, **kwargs)
        self._cache.put(key, result)
        return result
    return wrapper
