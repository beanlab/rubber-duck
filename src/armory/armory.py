import inspect
import json
from functools import wraps

from agents import FunctionTool, function_tool

def make_on_invoke_tool(func):
    @wraps(func)
    async def wrapped_tool(context, arg_json: str):
        args = json.loads(arg_json)
        if inspect.iscoroutinefunction(func):
            return await func(**args)
        else:
            return func(**args)
    return wrapped_tool

class Armory:
    def __init__(self):
        self._tools = {}

    def set_tool(self, tool_instance: object):
        # Iterate over the INSTANCE, not the class
        for attr_name in dir(tool_instance):
            if attr_name.startswith("_"):
                continue

            method = getattr(tool_instance, attr_name)
            if not callable(method):
                continue

            if not getattr(method, "is_tool", False):
                continue

            # Wrap it as a function tool, passing the bound method
            tool = function_tool(method)
            tool.on_invoke_tool = make_on_invoke_tool(method)
            self._tools[attr_name] = tool

    def get_tools(self) -> dict[str, FunctionTool]:
        return self._tools

    def get_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")
