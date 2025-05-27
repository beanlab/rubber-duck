from agents import function_tool, FunctionTool

_tools: dict[str, FunctionTool] = {}


def register_tool(func) -> FunctionTool:
    tool = function_tool(func)
    tool.params_json_schema = {
        k: v
        for k, v in tool.params_json_schema['properties'].items()
        if k != '_get_completion'
    }
    _tools[func.__name__] = tool
    return tool


def load_tools():
    import importlib
    import pkgutil

    package = importlib.import_module(__package__)
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package.__name__}.{module_name}")


def get_tool(tool_name: str):
    if tool_name in _tools:
        return _tools[tool_name]

    raise KeyError(f"Tool '{tool_name}' not found in any armory module.")


load_tools()
