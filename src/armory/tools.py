import importlib
import pkgutil

from agents import function_tool, FunctionTool

_tools: dict[str, FunctionTool] = {}


def register_tool(func) -> FunctionTool:
    tool = function_tool(func)
    _tools[func.__name__] = tool
    return tool


def get_tool(tool_name: str):
    if tool_name in _tools:
        return _tools[tool_name]

    # The way we're accessing a tool before it is actually used means that we need to import them so that the @register_tool will run
    # and add that tool to tool_registry. This is here to dynamically import all tools so that they are available. I don't know if there
    # is a better way to do this

    import src.armory
    package = src.armory

    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package.__name__}.{module_name}")

        if tool_name in _tools:
            return _tools[tool_name]

    raise KeyError(f"Tool '{tool_name}' not found in any armory module.")