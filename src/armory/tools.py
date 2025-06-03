from agents import FunctionTool

_tools: dict[str, FunctionTool] = {}


def register_tool(func):
    func.is_tool = True
    return func
