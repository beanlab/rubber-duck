import inspect
from functools import wraps
from typing import Callable

from openai.types.responses import FunctionToolParam

from .tools import generate_function_schema
from ..utils.config_types import DuckContext


class Armory:
    def __init__(self, send_message: Callable):
        self._tools: dict[str, Callable] = {}
        self._schemas: dict[str, FunctionToolParam] = {}

        self._send_message = send_message

    def scrub_tools(self, tool_instance: object):
        for attr_name in dir(tool_instance):
            if attr_name.startswith("_"):
                continue

            method = getattr(tool_instance, attr_name)
            if not callable(method):
                continue

            if not hasattr(method, "is_tool"):
                continue

            self.add_tool(method)

    def _wrap_tool_with_context(self, func: Callable) -> Callable:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        if params and params[0].name == "ctx":
            return func

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(ctx: DuckContext, *args, **kwargs):
                return await func(*args, **kwargs)
        else:
            @wraps(func)
            def wrapper(ctx: DuckContext, *args, **kwargs):
                return func(*args, **kwargs)

        return wrapper

    def add_tool(self, tool_function: Callable):
        wrapped = self._wrap_tool_with_context(tool_function)

        if hasattr(tool_function, "sends_image"):
            wrapped = self.send_image_directly(wrapped)

        self._schemas[tool_function.__name__] = generate_function_schema(tool_function)

        completes_response = hasattr(tool_function, 'complete_response')

        if inspect.iscoroutinefunction(wrapped):
            async def wrapper(*args, **kwargs):
                return await wrapped(*args, **kwargs), completes_response
        else:
            def wrapper(ctx: DuckContext, *args, **kwargs):
                return wrapped(*args, **kwargs), completes_response

        self._tools[tool_function.__name__] = wrapper

    def get_specific_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_tool_schema(self, tool_name: str) -> FunctionToolParam:
        if tool_name in self._schemas:
            return self._schemas[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def send_image_directly(self, func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs) -> None:
            if inspect.iscoroutinefunction(func):
                result = await func(ctx, *args, **kwargs)
            else:
                result = func(ctx, *args, **kwargs)

            name, _ = result
            await self._send_message(ctx.thread_id, file=result)
            return None

        return wrapper
