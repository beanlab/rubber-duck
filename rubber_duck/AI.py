import asyncio
from typing import Protocol, TypedDict
from quest import step
import openai
import logging
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from protocols import IndicateTyping, SendMessage


class RetryConfig(TypedDict):
    max_retries: int
    delay: int
    backoff: int


class GenAI():
    def __init__(self, openai_api_key: str,
                 retry_config: RetryConfig,
                 typing: IndicateTyping,
                 send_message: SendMessage):
        self._client = AsyncOpenAI(api_key=openai_api_key)
        self._retry_config = retry_config
        self._typing = typing
        self._send_message = step(send_message)


    @step
    async def _get_completion(self, thread_id, engine, message_history) -> tuple[list, dict]:
        async with self._typing(thread_id):
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
    async def get_completion_with_retry(self, thread_id, engine, message_history):
        max_retries = self._retry_config['max_retries']
        delay = self._retry_config['delay']
        backoff = self._retry_config['backoff']
        retries = -1
        while retries < max_retries:
            try:
                return await self._get_completion(thread_id, engine, message_history)
            except (openai.APITimeoutError, openai.InternalServerError, openai.UnprocessableEntityError) as ex:
                if retries == -1:
                    await self._send_message(thread_id, 'Trying to contact servers...')
                retries += 1
                if retries >= max_retries:
                    raise

                logging.warning(
                    f"Retrying due to {ex}, attempt {retries}/{max_retries}. Waiting {delay} seconds.")
                await asyncio.sleep(delay)
                delay *= backoff