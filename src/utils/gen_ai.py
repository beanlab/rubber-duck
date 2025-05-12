import asyncio
import json
import logging

from openai import AsyncOpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.chat import ChatCompletion
from quest import step

from ..conversation.conversation import GenAIException, RetryableException, GenAIClient, GPTMessage, \
    RetryConfig
from ..utils.protocols import IndicateTyping, ReportError, SendMessage


class OpenAI():
    def __init__(self, openai_api_key: str, tools: list = None):
        self._client = AsyncOpenAI(api_key=openai_api_key)
        self.tools = tools or []

    async def get_completion(self, engine, message_history) -> tuple[list, dict]:
        try:
            functions = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.params_json_schema
                }
                for tool in self.tools
            ]

            completion: ChatCompletion = await self._client.chat.completions.create(
                model=engine,
                messages=message_history,
                functions=functions if functions else None
            )
            choice = completion.choices[0]
            message = choice.message

            if message.function_call:
                function_name = message.function_call.name
                arguments = json.loads(message.function_call.arguments)

                for tool in self.tools:
                    if tool.name == function_name:
                        tool_result = await tool.on_invoke_tool(None, json.dumps(arguments))
                        break
                else:
                    raise Exception(f"Tool '{function_name}' not found.")

                message_history.append({"role": "assistant", "function_call": message.function_call})
                message_history.append({"role": "function", "name": function_name, "content": tool_result})

                second_completion = await self._client.chat.completions.create(
                    model=engine,
                    messages=message_history
                )

                second_completion_dict = second_completion.dict()
                return second_completion_dict['choices'], second_completion_dict['usage']
            else:
                completion_dict = completion.dict()
                return completion_dict['choices'], completion_dict['usage']

        except (
                APITimeoutError, InternalServerError,
                UnprocessableEntityError) as ex:
            raise RetryableException(ex, 'I\'m having trouble connecting to the OpenAI servers, '
                                         'please open up a separate conversation and try again') from ex
        except (APIConnectionError, BadRequestError,
                AuthenticationError, ConflictError, NotFoundError,
                RateLimitError) as ex:
            raise GenAIException(ex, "Visit https://platform.openai.com/docs/guides/error-codes/api-errors "
                                     "for more details on how to resolve this error") from ex


class RetryableGenAI:
    def __init__(self, genai: GenAIClient,
                 send_message: SendMessage, report_error: ReportError, typing: IndicateTyping,
                 retry_config: RetryConfig):
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._typing = typing
        self._retry_config = retry_config
        self._genai = genai

    async def get_completion(self, guild_id: int, thread_id: int, engine: str, message_history: list[GPTMessage]):
        max_retries = self._retry_config['max_retries']
        delay = self._retry_config['delay']
        backoff = self._retry_config['backoff']
        retries = 0
        while True:
            try:
                async with self._typing(thread_id):
                    return await self._genai.get_completion(engine, message_history)
            except RetryableException as ex:
                if retries == 0:
                    await self._send_message(thread_id, 'Trying to contact servers...')
                retries += 1
                if retries > max_retries:
                    raise GenAIException(ex, 'Retry limit exceeded')

                logging.warning(
                    f"Retrying due to {ex}, attempt {retries}/{max_retries}. Waiting {delay} seconds.")
                await asyncio.sleep(delay)
                delay *= backoff
