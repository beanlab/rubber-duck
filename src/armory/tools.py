from agents import function_tool, FunctionTool

_tools: dict[str, FunctionTool] = {}


def register_tool(func) -> FunctionTool:
    func.is_tool = True
    return func



