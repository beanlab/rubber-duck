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





