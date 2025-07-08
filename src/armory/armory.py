import inspect
from inspect import Parameter
from functools import wraps
from typing import Callable, Awaitable

from agents import FunctionTool, function_tool, Agent, RunContextWrapper

from src.utils.config_types import DuckContext


class Armory:
    def __init__(self, send_message):
        self._tools: dict[str, FunctionTool] = {}
        self.send_message = send_message

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

        if hasattr(tool_function, "direct_send_message"):
            tool_function = self.send_directly(tool_function)

        tool = function_tool(tool_function)

        self._tools[tool_function.__name__] = tool

    def add_agent_as_tool(self, agent: Agent, name: str, description: str):
        self._tools[name] = agent.as_tool(name, description)

    def get_specific_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_all_tool_names(self):
        return list(self._tools.keys())


    def send_directly(self, func):
        sig = inspect.signature(func)

        # Create a new Parameter for ctx with the correct type
        ctx_param = inspect.Parameter(
            name="wrapper",
            kind=Parameter.POSITIONAL_OR_KEYWORD,
            annotation=RunContextWrapper[DuckContext],
        )

        new_params = list(sig.parameters.values())

        # Insert ctx as FIRST parameter, not second
        param_names = [p.name for p in new_params]
        if "wrapper" not in param_names:
            new_params.insert(0, ctx_param)  # Changed from 1 to 0

        new_sig = sig.replace(parameters=new_params)

        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                bound = new_sig.bind(*args, **kwargs)
                bound.apply_defaults()
                wrapper = bound.arguments["wrapper"]

                # Prepare args to call the original method (without wrapper)
                call_args = {
                    k: v for k, v in bound.arguments.items() if k != "wrapper"
                }

                result = await func(**call_args)
                name, data = result
                await self.send_message(wrapper.context.thread_id, file=result)  # Fixed: use self.send_message
                return name

            async_wrapper.__signature__ = new_sig
            return async_wrapper

        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                bound = new_sig.bind(*args, **kwargs)
                bound.apply_defaults()
                wrapper = bound.arguments["wrapper"]

                call_args = {
                    k: v for k, v in bound.arguments.items() if k != "wrapper"
                }

                result = func(**call_args)
                name, data = result
                self.send_message(wrapper.context.thread_id, file=result)
                return name

            sync_wrapper.__signature__ = new_sig
            return sync_wrapper
