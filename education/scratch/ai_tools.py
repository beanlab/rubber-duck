from src.utils.gen_ai import GenAIClient


def ai_tool(cls):
    cls._ai_tool = True
    # in theory, could check that __init__ takes one arg: the GenAIClient
    # and __call__ is implemented
    return cls


@ai_tool
class GetExample:
    def __init__(self, gen_ai: GenAIClient):
        self._gen_ai = gen_ai

    async def __call__(self, prompt: str) -> str:
        response = await self._gen_ai.get_completion(...)
        return response[0]


def scrub(cls):
    if hasattr(cls, '_ai_tool'):
        pass
        # make tool schema from __call__ method on cls
        # change tool name from '__call__' to cls.__name__
        # note (somehow) that tool is a gen_ai_tool, and store the class
    else:
        pass  # existing logic


def get_completion(...):
    response = get_completion(...)
    if response.is_tool:
        tool = response.get_tool()
        if tool.is_gen_ai():
            method = tool.cls(self)
        else:
            method = tool.func

        method(args)