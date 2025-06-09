import inspect
from functools import wraps

from agents import FunctionTool, RunContextWrapper
from makefun import with_signature

from ..utils.config_types import DuckContext

_tools: dict[str, FunctionTool] = {}


def register_tool(_func=None, *, send_error_to_llm=False):
    def decorator(func):
        setattr(func, "is_tool", True)
        setattr(func, "send_error_to_llm", send_error_to_llm)
        return func

    if _func is not None:
        return decorator(_func)

    return decorator


def direct_send_message(func):
    sig = inspect.signature(func)
    is_class_method = 'self' in sig

    new_sig = str(sig)[1:-1]  # remove parens
    args = new_sig.split(',')

    if is_class_method:
        args = args[1:]  # remove self

    args = [f'context: RunContextWrapper[{DuckContext.__name__}]'] + args
    full_sig = f'({",".join(args)})'

    @with_signature(full_sig)
    @wraps(func)
    async def new_func(wrapper: RunContextWrapper[DuckContext], *args, **kwargs):
        result = await func(*args, **kwargs)
        await wrapper.context.send_message(wrapper.context.thread_id, result)

    return new_func
