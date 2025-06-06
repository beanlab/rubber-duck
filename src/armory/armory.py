from typing import Callable

from agents import FunctionTool, function_tool

from src.utils.protocols import SendMessage


class Armory:
    def __init__(self):
        self._tools = {}
        self._toolboxes = {}

    def add_message_info_to_toolboxes(self, thread_id: int, send_message: SendMessage):
        for toolbox in self._toolboxes.values():
                toolbox.thread_id = thread_id
                toolbox.send_message = send_message

    def add_toolbox(self, toolbox: object):
        self._toolboxes[toolbox.__class__.__name__] = toolbox

    def _scrub_tools(self, tool_instance: object):
        for attr_name in dir(tool_instance):
            if attr_name.startswith("_"):
                continue

            method = getattr(tool_instance, attr_name)
            if not callable(method):
                continue

            if not hasattr(method, "is_tool"):
                continue

            self.add_tool(method)

    def scrub_toolboxes(self):
        for toolbox in self._toolboxes.values():
            self._scrub_tools(toolbox)


    def add_tool(self, tool_function: Callable):
        if tool_function.send_error_to_llm:
            tool = function_tool(tool_function, failure_error_function=None)
        else:
            tool = function_tool(tool_function)
        self._tools[tool_function.__name__] = tool, tool_function

    def get_specific_tool_metadata(self, tool_name: str) -> FunctionTool:
        if tool_name in self._tools:
            return self._tools[tool_name][0]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_specific_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name][1]
        raise KeyError(f"Tool '{tool_name}' not found in any armory module.")

    def get_all_tool_names(self):
        return list(self._tools.keys())

