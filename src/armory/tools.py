

import inspect
from typing import Any, Callable, get_type_hints, Literal, Union, get_origin, get_args

from openai.types.responses import FunctionToolParam

_tools: dict[str, Callable] = {}


def register_tool(func):
    setattr(func, "is_tool", True)
    return func


def sends_image(func):
    func.sends_image = True
    return func



def is_optional(annotation) -> bool:
    origin = get_origin(annotation)
    args = get_args(annotation)
    return origin is Union and type(None) in args


def get_strict_json_schema_type(annotation) -> dict:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if is_optional(annotation):
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            return get_strict_json_schema_type(non_none_args[0])
        raise TypeError(f"Unsupported Union with multiple non-None values: {annotation}")

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }

    if annotation in type_map:
        return {"type": type_map[annotation]}
    if origin in type_map:
        return {"type": type_map[origin]}

    if origin is Literal:
        values = args
        if all(isinstance(v, (str, int, bool)) for v in values):
            return {"type": "string" if all(isinstance(v, str) for v in values) else "number", "enum": list(values)}
        raise TypeError("Unsupported Literal values in annotation")

    raise TypeError(f"Unsupported parameter type: {annotation}")


def generate_function_schema(func: Callable[..., Any]) -> FunctionToolParam:
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    params = {}
    required = []

    for name, param in sig.parameters.items():
        if name in {"self", "ctx"}:
            continue

        ann = type_hints.get(name, param.annotation)
        if ann is inspect._empty:
            raise TypeError(f"Missing type annotation for parameter: {name}")

        schema_entry = get_strict_json_schema_type(ann)

        required.append(name)
        params[name] = schema_entry

    return {
        "type": "function",
        "name": func.__name__,
        "description": func.__doc__ or "",
        "parameters": {
            "type": "object",
            "properties": params,
            "required": required,
            "additionalProperties": False
        },
        "strict": True
    }
