import inspect
from functools import wraps
from typing import Callable

from openai.types.responses import FunctionToolParam

from .talk_tool import TalkTool
from .tools import generate_function_schema
from ..utils.config_types import DuckContext


class Armory:
    def __init__(self, send_message: Callable):
        self._tools: dict[str, Callable] = {}
        self._send_message = send_message
        self._talk_tool = TalkTool(send_message)

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

        self._tools[tool_function.__name__] = wrapped

    def add_human_in_the_loop_tool(self, tool_function: Callable):
        if self._tools.get("hitl_" + tool_function.__name__, None) is None:
            wrapped = self.human_in_the_loop(tool_function)
            wrapped.__name__ = "hitl_" + tool_function.__name__
            self._tools[wrapped.__name__] = wrapped
        return "hitl_" + tool_function.__name__

    def get_specific_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_tool_schema(self, tool_name: str) -> FunctionToolParam:
        tool_function = self.get_specific_tool(tool_name)
        return generate_function_schema(tool_function)

    def send_image_directly(self, func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            if inspect.iscoroutinefunction(func):
                result = await func(ctx, *args, **kwargs)
            else:
                result = func(ctx, *args, **kwargs)

            name, _ = result
            await self._send_message(ctx.thread_id, file=result)
            return name

        return wrapper

    def human_in_the_loop(self, func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            args_str = ", ".join(repr(a) for a in args) if args else ""
            kwargs_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items()) if kwargs else ""
            all_args = ", ".join(filter(None, [args_str, kwargs_str])) or "None"

            await self._talk_tool.send_message_to_user(ctx, f"Is it okay to proceed, the Agent wants to call the {func.__name__} tool with these arguments {all_args}? (y/n)")
            response = await self._talk_tool.receive_message_from_user(ctx)
            if response.lower() in ['y', 'yes']:
                if inspect.iscoroutinefunction(func):
                    result = await func(ctx, *args, **kwargs)
                else:
                    result = func(ctx, *args, **kwargs)
            else:
                await self._talk_tool.send_message_to_user(ctx,
                                                           f"What is the reason for not approving the {func.__name__} tool call?")
                response = await self._talk_tool.receive_message_from_user(ctx)
                result = f"The user did not approve the **{func.__name__}** tool call for the following reason: {response}. **Continue talking** with the user or provide an alternative solution."
            return result
        return wrapper
