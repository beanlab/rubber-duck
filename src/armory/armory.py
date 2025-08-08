import inspect
from functools import wraps
from typing import Callable

from openai.types.responses import FunctionToolParam

from .tools import needs_context, generate_function_schema
from ..utils.config_types import DuckContext


class Armory:
    def __init__(self, send_message: Callable):
        self._tools: dict[str, Callable] = {}
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

    def add_tool(self, tool_function: Callable):
        if hasattr(tool_function, "sends_image"):
            tool_function = self.send_image_directly(tool_function)
        self._tools[tool_function.__name__] = tool_function

    def get_specific_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_tool_schema(self, tool_name: str) -> FunctionToolParam:
        tool_function = self.get_specific_tool(tool_name)
        return generate_function_schema(tool_function)

    def get_tool_needs_context(self, tool_name: str) -> bool:
        tool_function = self.get_specific_tool(tool_name)
        return needs_context(tool_function)

    def send_image_directly(self, func):
        sig = inspect.signature(func)

        ctx_param = inspect.Parameter(
            name="ctx",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation= DuckContext,
        )

        new_params = list(sig.parameters.values())

        param_names = [p.name for p in new_params]
        if "ctx" not in param_names:
            new_params.insert(0, ctx_param)

        new_sig = sig.replace(parameters=new_params)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            bound = new_sig.bind(*args, **kwargs)
            bound.apply_defaults()
            wrapper_arg = bound.arguments["ctx"]
            call_args = {
                k: v for k, v in bound.arguments.items() if k != "ctx"
            }
            if inspect.iscoroutinefunction(func):
                result = await func(**call_args)
            else:
                result = func(**call_args)

            name, _ = result
            await self._send_message(wrapper_arg.thread_id, file=result)
            return name

        wrapper.__signature__ = new_sig
        return wrapper
