import asyncio
import logging
from io import BytesIO
from typing import TypedDict, Protocol

from agents import Agent, Runner, ToolCallOutputItem
from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError, AsyncOpenAI
from openai.types.chat import ChatCompletion
from quest import step

from ..utils.config_types import DuckContext, AgentMessage, GPTMessage, FileData
from ..utils.logger import duck_logger
from ..utils.protocols import IndicateTyping, SendMessage

Sendable = str | tuple[str, BytesIO]


class GenAIClient(Protocol):
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


def _result_to_agent_message(result):
    last_item = result.new_items[-1]
    if isinstance(last_item, ToolCallOutputItem):
        if not isinstance(last_item.output, tuple):
            return AgentMessage(
                agent_name=result.last_agent.name,
                content=last_item.output
            )
        return AgentMessage(
            agent_name=result.last_agent.name,
            file=FileData(filename=last_item.output[0], bytes=last_item.output[1])
        )
    else:
        return AgentMessage(
            agent_name=result.last_agent.name,
            content=result.final_output
        )


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


class ChatCompletions:
    def __init__(self, openai_api_key: str):
        self._client = AsyncOpenAI(api_key=openai_api_key)

    async def autocorrect(self, possible_values: list[str], user_input: str) -> str:
        try:
            # Create a system prompt that instructs the model to find the closest match
            system_prompt = """You are a string matching assistant. Your task is to find the closest matching string from a given list of possible values to a user's input.
                            Rules:
                            1. Return ONLY the exact string from the possible values list that best matches the user input
                            2. Consider spelling mistakes, typos, abbreviations, and partial matches
                            3. If multiple options are equally close, pick the most likely intended match
                            4. Always return one of the provided possible values, never create new strings
                            5. Be case-insensitive in your matching but return the exact case from the possible values
                            Respond with ONLY the matching string, no explanations or additional text."""

            user_prompt = f"""Possible values: {", ".join(possible_values)}
                          User input: "{user_input}"
                          Find the closest match from the possible values list."""

            completion: ChatCompletion = await self._client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,
                max_tokens=50
            )

            response = completion.choices[0].message.content.strip()

            if response in possible_values:
                return response
            else:
                return self._fallback_match(possible_values, user_input)

        except Exception as e:
            print(f"Error in autocorrect: {e}")
            return self._fallback_match(possible_values, user_input)

    def _fallback_match(self, possible_values: list[str], user_input: str) -> str:
        user_input_lower = user_input.lower()

        for value in possible_values:
            if value.lower() == user_input_lower:
                return value

        for value in possible_values:
            if user_input_lower in value.lower() or value.lower() in user_input_lower:
                return value

        return possible_values[0] if possible_values else ""


class AgentClient:
    def __init__(
            self,
            agent: Agent,
            typing: IndicateTyping
    ):
        self._agent = agent
        self._typing = typing

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
            message_history: list,
            **kwargs
    ) -> AgentMessage:
        async with self._typing(context.thread_id):
            result = await Runner.run(
                self._agent,
                message_history,
                context=context,
                **kwargs
            )

            return _result_to_agent_message(result)


class RetryableGenAI:
    def __init__(self,
                 genai: GenAIClient,
                 send_message: SendMessage,
                 retry_config: RetryConfig
                 ):
        self._send_message = step(send_message)
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
