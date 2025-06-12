import asyncio
import logging
from io import BytesIO
from typing import TypedDict, Protocol

from agents import Agent, Runner, RunResult, ToolCallOutputItem
from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from quest import step

from .agent_storage import LastAgentStorage
from .config_types import DuckContext, AgentMessage, GPTMessage
from .logger import duck_logger
from ..utils.protocols import IndicateTyping, ReportError, SendMessage

Sendable = str | tuple[str, BytesIO]


class GenAIClient(Protocol):
    introduction: str | None

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list[GPTMessage],
    ) -> AgentMessage: ...


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
    def __init__(self, agent: Agent, introduction: str, record_usage: RecordUsage, typing: IndicateTyping):
        self._agent = agent
        self.introduction = introduction
        self._record_usage = record_usage
        self._typing = typing

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list,
    ) -> AgentMessage:
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
    ) -> AgentMessage:
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
                return AgentMessage(content=last_item.output[0], file=last_item.output[1])
            else:
                return AgentMessage(content=result.final_output, file=None)


class MultiAgentClient:
    def __init__(self, agents: dict[str, Agent], last_agent_storage: LastAgentStorage, starting_agent: str,
                 introduction: str, record_usage: RecordUsage, typing: IndicateTyping):
        self._agents = agents
        self._last_agent_storage = last_agent_storage
        self._starting_agent = starting_agent
        self.introduction = introduction
        self._record_usage = record_usage
        self._typing = typing

    def _find_last_agent(self, storage) -> Agent:

        last_agent_name = storage.get()

        if last_agent_name and last_agent_name in self._agents.keys():
            return self._agents[last_agent_name]

        return self._agents[self._starting_agent]

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list
    ) -> AgentMessage:
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
    ) -> AgentMessage:

        with self._last_agent_storage as storage:
            current_agent = self._find_last_agent(storage)
            async with self._typing(context.thread_id):
                result = await run_agent(
                    current_agent,
                    message_history,
                    context=context,
                    max_turns=5
                )
                usage = result.context_wrapper.usage
                await self._record_usage(
                    context.guild_id,
                    context.channel_id,
                    context.thread_id,
                    context.author_id,
                    self._agents[current_agent.name].model,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.input_tokens_cached if hasattr(usage, 'input_tokens_cached') else 0,
                    usage.reasoning_tokens if hasattr(usage, 'reasoning_tokens') else 0
                )

                storage.set(result.last_agent.name)
            last_item = result.new_items[-1]
            if isinstance(last_item, ToolCallOutputItem):
                return AgentMessage(content=last_item.output[0], file=last_item.output[1])
            else:
                return AgentMessage(content=result.final_output, file=None)


class RetryableGenAI:
    def __init__(self,
                 genai: GenAIClient,
                 send_message: SendMessage,
                 report_error: ReportError,
                 typing: IndicateTyping,
                 retry_config: RetryConfig
                 ):
        self.introduction = genai.introduction

        self._send_message = step(send_message)
        self._report_error = step(report_error)
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
