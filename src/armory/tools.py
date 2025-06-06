import functools

from agents import FunctionTool

_tools: dict[str, FunctionTool] = {}


def register_tool(_func=None, *, send_error_to_llm=False):
    def decorator(func):
        setattr(func, "is_tool", True)
        setattr(func, "send_error_to_llm", send_error_to_llm)
        return func

    if _func is not None:
        return decorator(_func)

    return decorator


def send_message_to_thread(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        thread_id = getattr(self, 'thread_id', None)
        send_message = getattr(self, 'send_message', None)
        if thread_id and send_message:
            send_message(thread_id, str(result))
        else:
            raise ValueError("thread_id or send_message missing from the context")

    return wrapper


