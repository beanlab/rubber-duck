from typing import Callable

from agents import FunctionTool, function_tool

from ..armory.tools import selective_error_handler


class Armory:
    def __init__(self):
        self._tools: dict[str, FunctionTool] = {}

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
        tool = function_tool(tool_function, failure_error_function=selective_error_handler)
        self._tools[tool_function.__name__] = tool

    def get_specific_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_all_tool_names(self):
        return list(self._tools.keys())
