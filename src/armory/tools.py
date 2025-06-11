import asyncio
import inspect
from functools import wraps

from agents import FunctionTool, RunContextWrapper, Usage
from makefun import with_signature

from ..utils.config_types import DuckContext

_tools: dict[str, FunctionTool] = {}


def register_tool(_func=None, *, send_error_to_llm=True):
    def decorator(func):
        setattr(func, "is_tool", True)
        setattr(func, "send_error_to_llm", send_error_to_llm)
        return func

    if _func is not None:
        return decorator(_func)

    return decorator



def direct_send_message(func):
    func.direct_send_message = True
    return func
