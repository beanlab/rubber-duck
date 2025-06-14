import asyncio
import json
import logging
from io import BytesIO
from typing import TypedDict, Protocol, Any

from agents import Agent, Runner, RunResult, ToolCallOutputItem
from openai import AsyncOpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.chat import ChatCompletion
from quest import step

from .config_types import DuckContext
from .logger import duck_logger
from ..armory.armory import Armory
from ..utils.protocols import IndicateTyping, SendMessage

Sendable = str | tuple[str, BytesIO]


class GPTMessage(TypedDict):
    role: str
    content: str


class GenAIClient(Protocol):
    introduction: str | None

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list[GPTMessage],
    ) -> str: ...


class GenAIException(Exception):
    def __init__(self, exception, web_mention):
        self.exception = exception
        self.web_mention = web_mention
        super().__init__(self.exception.__str__())


class RetryConfig(TypedDict):
    max_retries: int
    delay: int
    backoff: int


class RetryableException(Exception):
    def __init__(self, exception, message):
        self.exception = exception
        self.message = message
        super().__init__(self.exception.__str__())


class RecordMessage(Protocol):
    async def __call__(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str): ...


class RecordUsage(Protocol):
    async def __call__(self, guild_id: int, parent_channel_id: int, thread_id: int, user_id: int, engine: str,
                       input_tokens: int,
                       output_tokens: int, cached_tokens: int, reasoning_tokens: int): ...


class HubSpokeAgentClient:
    pass


async def run_agent(*args, **kwargs) -> RunResult:
    return await Runner.run(*args, **kwargs)


class AgentClient:
    def __init__(self, introduction: str, agent: Agent, record_usage: RecordUsage, typing: IndicateTyping):
        self.introduction = introduction
        self._agent = agent
        self._record_usage = record_usage
        self._typing = typing

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list,
    ) -> str:
        try:
            return await self._get_completion(
                context,
                message_history
            )
        except (
                APITimeoutError, InternalServerError,
                UnprocessableEntityError) as ex:
            raise RetryableException(ex, 'I\'m having trouble connecting to the OpenAI servers, '
                                         'please open up a separate conversation and try again') from ex
        except (APIConnectionError, BadRequestError,
                AuthenticationError, ConflictError, NotFoundError,
                RateLimitError) as ex:
            duck_logger.exception(f"AgentClient get_completion Exception: {ex}")
            raise GenAIException(ex, "Visit https://platform.openai.com/docs/guides/error-codes/api-errors "
                                     "for more details on how to resolve this error") from ex

    async def _get_completion(
            self,
            context: DuckContext,
            message_history: list
    ) -> Any:
        async with self._typing(context.thread_id):
            duck_logger.debug("New Agent Request")
            result = await run_agent(
                self._agent,
                message_history,
                context=context,
                max_turns=100
            )
            usage = result.context_wrapper.usage
            await self._record_usage(
                context.guild_id,
                context.channel_id,
                context.thread_id,
                context.author_id,
                self._agent.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.input_tokens_cached if hasattr(usage, 'input_tokens_cached') else 0,
                usage.reasoning_tokens if hasattr(usage, 'reasoning_tokens') else 0
            )
            last_item = result.new_items[-1]
            if isinstance(last_item, ToolCallOutputItem):
                return result.new_items[-1].output
            else:
                return result.final_output


class OpenAI:
    def __init__(self,
                 openai_api_key: str,
                 armory: Armory,
                 record_usage: RecordUsage,
                 ):
        self._client = AsyncOpenAI(api_key=openai_api_key)
        self._armory = armory
        self._record_usage = step(record_usage)

    async def _get_completion_with_usage(
            self,
            guild_id: int,
            parent_channel_id: int,
            thread_id: int,
            user_id: int,
            engine: str,
            message_history,
            functions
    ):
        if not functions:
            functions = None

        completion: ChatCompletion = await self._client.chat.completions.create(
            model=engine,
            messages=message_history,
            functions=functions
        )

        completion_dict = completion.model_dump()

        await self._record_usage(
            guild_id,
            parent_channel_id,
            thread_id,
            user_id,
            engine,
            completion_dict['usage']['prompt_tokens'],
            completion_dict['usage']['completion_tokens'],
            completion_dict['usage'].get('cached_tokens', 0),
            completion_dict['usage'].get('reasoning_tokens', 0)
        )
        return completion

    async def _get_completion(
            self,
            guild_id: int,
            parent_channel_id: int,
            thread_id: int,
            user_id: int,
            engine: str,
            message_history: list[GPTMessage],
            tools: list[str]
    ) -> list[Sendable]:
        tools_to_use = {tool: self._armory.get_specific_tool(tool) for tool in tools}

        functions = [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.params_json_schema
            }
            for tool in tools_to_use.values()
        ]

        result: list[Sendable] = []

        while True:
            completion = await self._get_completion_with_usage(
                guild_id, parent_channel_id, thread_id, user_id, engine, message_history, functions
            )
            message = completion.choices[0].message

            if message.function_call:

                function_name = message.function_call.name
                tool = self._armory.get_specific_tool(function_name)
                arguments = json.loads(message.function_call.arguments)
                try:
                    tool_result = tool(**arguments)
                except Exception as ex:
                    tool_result = f"Error when calling function {tool.__name__}, with arguments {arguments}. The error message was of type {ex.__class__.__name__} with the message: {str(ex)}"

                message_history.append({"role": "assistant", "function_call": message.function_call})
                message_history.append({"role": "function", "name": function_name, "content": str(tool_result)})

                if isinstance(tool_result, tuple):
                    result.append(tool_result)

                continue  # i.e. allow the bot to call another tool or add a message

            else:
                message_history.append({
                    "role": "assistant",
                    "content": message.content
                })

                result.append(message.content)
                break  # i.e. the bot is done responding

        return result

    async def get_completion(
            self,
            guild_id: int,
            parent_channel_id: int,
            thread_id: int,
            user_id: int,
            engine: str,
            message_history: list[GPTMessage],
            tools: list[str]
    ) -> list[Sendable]:
        try:
            return await self._get_completion(guild_id, parent_channel_id, thread_id, user_id, engine, message_history,
                                              tools)
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
    def __init__(self,
                 genai: GenAIClient,
                 send_message: SendMessage,
                 typing: IndicateTyping,
                 retry_config: RetryConfig
                 ):
        self.introduction = genai.introduction

        self._send_message = step(send_message)
        self._typing = typing
        self._retry_config = retry_config
        self._genai = genai

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list[GPTMessage],
    ):
        max_retries = self._retry_config['max_retries']
        delay = self._retry_config['delay']
        backoff = self._retry_config['backoff']
        retries = 0
        while True:
            try:
                async with self._typing(context.thread_id):
                    return await self._genai.get_completion(
                        context, message_history
                    )

            except RetryableException as ex:
                if retries == 0:
                    await self._send_message(context.thread_id, 'Trying to contact servers...')
                retries += 1
                if retries > max_retries:
                    raise GenAIException(ex, 'Retry limit exceeded')

                logging.warning(
                    f"Retrying due to {ex}, attempt {retries}/{max_retries}. Waiting {delay} seconds.")
                await asyncio.sleep(delay)
                delay *= backoff
