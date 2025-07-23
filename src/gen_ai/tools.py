import inspect
import json
from typing import get_origin, Callable, get_type_hints

from openai.types.responses import ResponseFunctionToolCall, FunctionToolParam

PYTHON_TO_JSON_TYPES = {
    int: "integer",
    float: "number",
    str: "string",
    bool: "boolean",
    list: "array",
    dict: "object",
}

class Tool:
    def __init__(self, func: Callable):
        self.func = func
        self.name = func.__name__
        self.description = func.__doc__ or ""
        self.parameters_schema = self._generate_openai_parameters(func)

    def _get_json_type(self, py_type) -> str:
        origin = get_origin(py_type) or py_type
        return PYTHON_TO_JSON_TYPES.get(origin, "string")

    def _generate_openai_parameters(self, func: Callable) -> dict:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            annotation = type_hints.get(name, str)
            param_type = self._get_json_type(annotation)
            properties[name] = {
                "type": param_type,
                "description": ""  # Could be extracted from docstrings
            }
            if param.default is inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False
        }

    def to_openai_tool(self) -> FunctionToolParam:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
            "strict": True
        }

    def run(self, **kwargs):
        return self.func(**kwargs)

class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self.register(self.create_talk_to_user_tool())
        self.register(self.create_end_conversation_tool())

    def scrub_tools(self, tool_instance: object):
        for attr_name in dir(tool_instance):
            if attr_name.startswith("_"):
                continue

            method = getattr(tool_instance, attr_name)
            if not callable(method):
                continue

            if not hasattr(method, "is_tool"):
                continue

            self.register(method)

    def register(self, func: Callable):
        tool = Tool(func)
        self.tools[tool.name] = tool
        return tool

    def handle_tool_call(self, call: ResponseFunctionToolCall):
        name = call.name
        args_json = call.arguments
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not registered")
        args = json.loads(args_json or "{}")
        return self.tools[name].run(**args)

    def get_tool(self, name: str) -> Tool:
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found")
        return self.tools[name]

    def get_all_tool_names(self) -> list[str]:
        return list(self.tools.keys())

    def create_talk_to_user_tool(self):
        def talk_to_user(output: str) -> str:
            """
            A tool to interact with the user directly. Call this tool to continue the conversation with the user.
            :param output: The agent's output to the user or in other words the assistants response to the last user response.
            :return input: The user's response to the agent's output.
            """
            print(f"Agent: {output}")
            inpt = input("You: ")
            return inpt
        return talk_to_user

    def create_end_conversation_tool(self):
        def end_conversation(reason: str) -> str:
            """
            End the conversation gracefully. Use this when the task is complete,
            no further assistance is needed, or the conversation has reached a natural conclusion.
            :param reason: Brief explanation of why the conversation is ending
            :return: Confirmation that conversation will end
            """
            return f"END_CONVERSATION: {reason}"
        return end_conversation







