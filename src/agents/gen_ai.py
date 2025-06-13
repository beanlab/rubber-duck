import asyncio
import logging
from io import BytesIO
from typing import TypedDict, Protocol

from agents import Agent, Runner, ToolCallOutputItem
from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from quest import step, BlobStorage, suspendable

from ..utils.config_types import DuckContext, AgentMessage, GPTMessage, FileData
from ..utils.logger import duck_logger
from ..utils.protocols import IndicateTyping, SendMessage

Sendable = str | tuple[str, BytesIO]


class GenAIClient(Protocol):
    introduction: str | None

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list[GPTMessage],
    ) -> AgentMessage: ...

    async def __aenter__(self) -> 'GenAIClient':
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        ...


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


def _result_to_agent_message(result):
    last_item = result.new_items[-1]
    if isinstance(last_item, ToolCallOutputItem):
        return AgentMessage(file=FileData(filename=last_item.output[0], bytes=last_item.output[1]))
    else:
        return AgentMessage(content=result.final_output)


async def _run_with_exception_handling(coroutine):
    try:
        return await coroutine
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


class AgentClient:
    def __init__(
            self,
            agent: Agent,
            introduction: str,
            typing: IndicateTyping
    ):
        self._agent = agent
        self.introduction = introduction
        self._typing = typing

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        ...

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list,
    ) -> AgentMessage:
        return await _run_with_exception_handling(self._get_completion(
            context,
            message_history
        ))

    async def _get_completion(
            self,
            context: DuckContext,
            message_history: list
    ) -> AgentMessage:
        async with self._typing(context.thread_id):
            result = await Runner.run(
                self._agent,
                message_history,
                context=context,
                max_turns=100
            )

            return _result_to_agent_message(result)


class MultiAgentClient:
    def __init__(self,
                 agents: dict[str, Agent],
                 starting_agent: str,
                 introduction: str,
                 typing: IndicateTyping,
                 thread_id: int,
                 blob_storage: BlobStorage
                 ):
        self.introduction = introduction

        self._storage_key = f'multi-agent-{thread_id}'
        self._agents = agents
        self._name_of_last_agent = starting_agent
        self._typing = typing
        self._blob_storage = blob_storage

    async def __aenter__(self):
        if self._blob_storage.has_blob(self._storage_key):
            self._name_of_last_agent = self._blob_storage.read_blob(self._storage_key)

    @suspendable
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._blob_storage.has_blob(self._storage_key):
            self._blob_storage.delete_blob(self._storage_key)

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list
    ) -> AgentMessage:
        return await _run_with_exception_handling(self._get_completion(
            context,
            message_history
        ))

    async def _get_completion(
            self,
            context: DuckContext,
            message_history: list
    ) -> AgentMessage:

        async with self._typing(context.thread_id):
            result = await Runner.run(
                self._agents[self._name_of_last_agent],
                message_history,
                context=context,
                max_turns=5
            )

            self._name_of_last_agent = result.last_agent.name
            self._blob_storage.write_blob(self._storage_key, self._name_of_last_agent)

        return _result_to_agent_message(result)


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
