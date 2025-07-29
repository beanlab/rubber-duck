
import inspect
from typing import Any, Callable, get_type_hints, get_origin, get_args, Literal
_tools: dict[str, Callable] = {}


def register_tool(func):
    setattr(func, "is_tool", True)
    return func


def sends_image(func):
    func.sends_image = True
    return func

def get_strict_json_schema_type(annotation) -> dict:
    origin = get_origin(annotation) or annotation

    if origin in [str, int, float, bool]:
        return {"type": origin.__name__}

    if origin is Literal:
        values = get_args(annotation)
        if all(isinstance(v, (str, int, bool)) for v in values):
            return {"enum": list(values)}
        else:
            raise TypeError("Unsupported Literal type")

    raise TypeError(f"Unsupported parameter type: {annotation}")

def generate_openai_function_schema(
    func: Callable[..., Any]
) -> dict:
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    params = {}
    required = []

    for i, (name, param) in enumerate(sig.parameters.items()):
        if name == "self":
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

    function_schema = {
        "name": func.__name__,
        "description": func.__doc__ or "",
        "parameters": {
            "type": "object",
            "properties": params,
            "required": required
        }
    }

    return function_schema

def get_needs_context(tool_function: Callable) -> bool:
    sig = inspect.signature(tool_function)
    params = list(sig.parameters.values())
    if not params:
        return False
    first_param_name = params[0].name
    return first_param_name in ("ctx", "context")