from agents import FunctionTool

_tools: dict[str, FunctionTool] = {}


def register_tool(func):
    setattr(func, "is_tool", True)
    return func


def sends_image(func):
    func.sends_image = True
    return func
