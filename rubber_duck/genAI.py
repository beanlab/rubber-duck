import logging
from typing import TypedDict

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from quest import step

from protocols import SendMessage


class RetryConfig(TypedDict):
    max_retries: int
    delay: int
    backoff: int


class OpenAI():
    def __init__(self, openai_api_key: str):
        self._client = AsyncOpenAI(api_key=openai_api_key)

    @step
    async def _get_completion(self, engine, message_history) -> tuple[list, dict]:
        completion: ChatCompletion = await self._client.chat.completions.create(
            model=engine,
            messages=message_history
        )
        logging.debug(f"Completion: {completion}")
        completion_dict = completion.dict()
        choices = completion_dict['choices']
        usage = completion_dict['usage']
        return choices, usage

    @step
    async def get_completion(self, engine, message_history) -> tuple[list, dict]:
        return await self._get_completion(engine, message_history)
