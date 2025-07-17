from agents import FunctionTool

_tools: dict[str, FunctionTool] = {}


def register_tool(func):
    func.is_tool = True
    return func



def direct_send_message(func):
    func.direct_send_message = True
    return func
