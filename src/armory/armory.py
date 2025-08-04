from typing import Callable

from openai.types.responses import FunctionToolParam

from .tools import generate_openai_function_schema, needs_context, needs_history


class Armory:

    def __init__(self):
        self._tools: dict[str, Callable] = {}

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
        self._tools[tool_function.__name__] = tool_function

    def get_specific_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_tool_schema(self, tool_name: str) -> FunctionToolParam:
        tool_function = self.get_specific_tool(tool_name)
        return generate_openai_function_schema(tool_function)

    def get_tool_needs_context(self, tool_name: str) -> bool:
        tool_function = self.get_specific_tool(tool_name)
        return needs_context(tool_function)

    def get_tool_needs_history(self, tool_name: str) -> bool:
        tool_function = self.get_specific_tool(tool_name)
        return needs_history(tool_function)

    def get_all_tool_names(self):
        return list(self._tools.keys())
