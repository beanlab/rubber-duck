
import inspect
from typing import Any, Callable, get_type_hints, get_origin, get_args, Literal

from openai.types.responses import FunctionToolParam

_tools: dict[str, Callable] = {}


def register_tool(func):
    setattr(func, "is_tool", True)
    return func


def sends_image(func):
    func.sends_image = True
    return func

def get_strict_json_schema_type(annotation) -> dict:
    origin = get_origin(annotation) or annotation

    # Map Python types to JSON Schema types
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }

    if origin in type_map:
        return {"type": type_map[origin]}

    if origin is Literal:
        values = get_args(annotation)
        if all(isinstance(v, (str, int, bool)) for v in values):
            return {"enum": list(values)}
        else:
            raise TypeError("Unsupported Literal type")

    raise TypeError(f"Unsupported parameter type: {annotation}")


def generate_openai_function_schema(func: Callable[..., Any]) -> FunctionToolParam:
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    params = {}
    required = []

    for name, param in sig.parameters.items():
        if name in {"self", "ctx", "context", "history", "message_history"}:
            continue

        ann = type_hints.get(name, param.annotation)
        if ann is inspect._empty:
            raise TypeError(f"Missing type annotation for parameter: {name}")

        try:
            schema_entry = get_strict_json_schema_type(ann)
        except TypeError as e:
            raise TypeError(f"Error in parameter '{name}': {e}")

        if param.default != inspect.Parameter.empty:
            schema_entry["default"] = param.default
        else:
            required.append(name)

        params[name] = schema_entry

    function_schema: FunctionToolParam = {
        "type": "function",
        "name": func.__name__,
        "description": func.__doc__ or "",
        "parameters": {
            "type": "object",
            "properties": params,
            "required": required,
            "additionalProperties": False,
        },
        "strict": True,
    }

    return function_schema


def needs_context(tool_function: Callable) -> bool:
    sig = inspect.signature(tool_function)
    params = list(sig.parameters.values())
    if not params:
        return False
    first_param_name = params[0].name
    return first_param_name in ("ctx", "context")

def needs_history(tool_function: Callable) -> bool:
    sig = inspect.signature(tool_function)
    params = list(sig.parameters.values())
    if not params:
        return False
    second_param_name = params[1].name
    return second_param_name in ("history", "message_history")
