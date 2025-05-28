import functools
import io
from typing import Protocol

from ..utils.logger import duck_logger


class PrepProtocol(Protocol):
    def run(self, value):
        ...


class CommonPrep:
    def run(self, value):
        return value


class BytesIOPrep:
    def run(self, value):
        for output in value:
            if isinstance(output, io.BytesIO):
                output.seek(0)
        return value


class Cache:
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def put(self, key, value):
        self.cache[key] = value


def cache_tool(prep: PrepProtocol = CommonPrep()):
    def cache_result(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            key = (method.__name__, *args, tuple(sorted(kwargs.items())))
            if value := self._cache.get(key):
                value = prep.run(value)
                return value
            duck_logger.debug(f"Caching result for {method.__name__} with key={key}")
            result = method(self, *args, **kwargs)
            self._cache.put(key, result)
            return result

        return wrapper

    return cache_result
