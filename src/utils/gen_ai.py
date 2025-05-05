import asyncio
import logging
from pathlib import Path

from openai import AsyncOpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.chat import ChatCompletion
from quest import step

from agents import (
    Agent,
    Runner,
    set_default_openai_key
)


from ..conversation.conversation import GenAIException, RetryableException, GenAIClient, GPTMessage, \
    RetryConfig, generate_error_message
from ..utils.protocols import IndicateTyping, ReportError, SendMessage



class OpenAI():
    def __init__(self, openai_api_key: str):
        self._client = AsyncOpenAI(api_key=openai_api_key)

    async def get_completion(self, engine, message_history) -> tuple[list, dict]:
        try:
            completion: ChatCompletion = await self._client.chat.completions.create(
                model=engine,
                messages=message_history
            )
            logging.debug(f"Completion: {completion}")
            completion_dict = completion.dict()
            choices = completion_dict['choices']
            usage = completion_dict['usage']
            return choices, usage
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

class AgentSDKAI():
    def __init__(self, openai_api_key: str, prompt_file: dict[str, str]):
        set_default_openai_key(openai_api_key)
        self.prompt1 = Path(prompt_file["teaching_assistant"]).read_text()
    async def get_completion(self, engine, message_history) -> tuple[list, dict]:
        try:
            agent = Agent(
                name="Teaching Assistant Agent",
                instructions=self.prompt1,
                model=engine,
            )

            run_result = await Runner.run(agent, message_history, max_turns=1)
            assistant_text = run_result.final_output
            choices = [{
                "message": {
                    "role": "assistant",
                    "content": assistant_text
                }
            }]
            usage_totals = {}
            total_input = 0
            total_output = 0
            for resp in run_result.raw_responses:
                u = resp.usage
                total_input += u.input_tokens
                total_output += u.output_tokens
            usage_totals['prompt_tokens'] = total_input
            usage_totals['completion_tokens'] = total_output
            return choices, usage_totals
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
                    error_message, _ = generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id, ex.message)
                    await self._report_error(error_message)
                    raise GenAIException(ex, error_message)

                logging.warning(
                    f"Retrying due to {ex}, attempt {retries}/{max_retries}. Waiting {delay} seconds.")
                await asyncio.sleep(delay)
                delay *= backoff
