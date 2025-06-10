import asyncio
import inspect
from functools import wraps

from agents import FunctionTool, RunContextWrapper, Usage
from makefun import with_signature

from ..utils.config_types import DuckContext

_tools: dict[str, FunctionTool] = {}


class ExitSilently(Exception):
    def __init__(self, usage: Usage, message: str):
        self.usage = usage
        self.message = message


def register_tool(_func=None, *, send_error_to_llm=True):
    def decorator(func):
        setattr(func, "is_tool", True)
        setattr(func, "send_error_to_llm", send_error_to_llm)
        return func

    if _func is not None:
        return decorator(_func)

    return decorator


def register_tools(func):
    func.is_tool = True
    return func


def selective_error_handler(ctx, error) -> str:
    if isinstance(error, ExitSilently):
        raise error
    else:
        return f"An error occurred: {str(error)}"


def direct_send_message(func):
    sig = inspect.signature(func)
    is_class_method = 'self' in str(sig)

    tokens = str(sig).split('->')
    if len(tokens) == 1:
        base_sig = tokens[0]
        return_type = ''
    else:
        base_sig, return_type = tokens
        return_type = f' ->' + return_type

    new_sig = base_sig.strip()[1:-1]  # remove parens
    args = new_sig.split(',')

    if is_class_method:
        args = args[:1] + [f'wrapper: RunContextWrapper[{DuckContext.__name__}]'] + args[1:]  # remove self
    else:
        args = [f'wrapper: RunContextWrapper[{DuckContext.__name__}]'] + args[1:]
    full_sig = f'({",".join(args)}){return_type}'

    @with_signature(full_sig)
    @wraps(func)
    async def new_func(wrapper: RunContextWrapper[DuckContext], *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)
        if isinstance(result, str):
            await wrapper.context.send_message(wrapper.context.thread_id, result)
            raise ExitSilently(wrapper.usage, result)
        elif isinstance(result, tuple):
            await wrapper.context.send_message(wrapper.context.thread_id, file=result)
            raise ExitSilently(wrapper.usage, result[0])

    return new_func
