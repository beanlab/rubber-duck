from agents import function_tool, FunctionTool

_tools: dict[str, FunctionTool] = {}


def register_tool(func) -> FunctionTool:
    tool = function_tool(func)
    _tools[func.__name__] = tool
    return tool


def get_tool(tool_name: str) -> FunctionTool:
    return _tools[tool_name]
