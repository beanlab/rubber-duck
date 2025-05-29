from typing import Callable

from agents import FunctionTool, function_tool


class Armory:
    def __init__(self):
        self._tools = {}

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
        tool = function_tool(tool_function)
        self._tools[tool_function.__name__] = tool, tool_function

    def get_tools(self) -> dict[str, Callable]:
        return {name: method for name, (meta, method) in self._tools.items()}

    def get_tool_metadata(self) -> dict[str, FunctionTool]:
        return {name: meta for name, (meta, method) in self._tools.items()}

    def get_specific_tool_metadata(self, tool_name: str) -> FunctionTool:
        if tool_name in self._tools:
            return self._tools[tool_name][0]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_specific_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name][1]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")
