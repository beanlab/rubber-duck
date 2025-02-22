import asyncio
import logging
import traceback as tb
import uuid
from typing import TypedDict, Protocol

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from quest import step, queue

from protocols import Message, SendMessage, ReportError, IndicateTyping


class RetryConfig(TypedDict):
    max_retries: int
    delay: int
    backoff: int


class GPTMessage(TypedDict):
    role: str
    content: str


class RecordMessage(Protocol):
    async def __call__(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str): ...


class RecordUsage(Protocol):
    async def __call__(self, guild_id: int, thread_id: int, user_id: int, engine: str, input_tokens: int,
                       output_tokens: int): ...


class HaveStandardGptConversation:
    def __init__(self, openai_api_key: str,
                 retry_config: RetryConfig,
                 record_message: RecordMessage, record_usage: RecordUsage,
                 send_message: SendMessage, report_error: ReportError, typing: IndicateTyping):
        self._retry_config = retry_config
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._typing = typing
        self._client = AsyncOpenAI(api_key=openai_api_key)

    async def __call__(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
        async with queue('messages', None) as messages:
            message_history = [
                GPTMessage(role='system', content=prompt)
            ]

            user_id = initial_message['author_id']
            guild_id = initial_message['guild_id']

            # Record the prompt
            await self._record_message(
                guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])
            while True:
                # TODO - if the conversation is getting long, and the user changes the subject
                #  prompt them to start a new conversation (and close this one)

                try:  # catch all errors
                    try:
                        # Waiting for a response from the user
                        message: Message = await asyncio.wait_for(messages.get(), timeout)

                    except asyncio.TimeoutError:  # Close the thread if the conversation has closed
                        break

                    if len(message['file']) > 0:
                        await self._send_message(
                            thread_id,
                            "I'm sorry, I can't read file attachments. "
                            "Please resend your message with the relevant parts of your file included in the message."
                        )
                        continue

                    message_history.append(GPTMessage(role='user', content=message['content']))

                    user_id = message['author_id']
                    guild_id = message['guild_id']

                    await self._record_message(
                        guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content']
                    )

                    choices, usage = await self._get_completion_with_retry(thread_id, engine, message_history)
                    response_message = choices[0]['message']
                    response = response_message['content'].strip()

                    await self._record_usage(guild_id, thread_id, user_id,
                                             engine,
                                             usage['prompt_tokens'],
                                             usage['completion_tokens'])

                    await self._record_message(
                        guild_id, thread_id, user_id, response_message['role'], response_message['content'])

                    message_history.append(GPTMessage(role='assistant', content=response))

                    await self._send_message(thread_id, response)

                except (openai.APITimeoutError, openai.InternalServerError, openai.UnprocessableEntityError) as ex:
                    error_message, _ = self._generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id,
                                             'I\'m having trouble connecting to the OpenAI servers, '
                                             'please open up a separate conversation and try again')
                    await self._report_error(error_message)
                    break

                except (openai.APIConnectionError, openai.BadRequestError,
                        openai.AuthenticationError, openai.ConflictError, openai.NotFoundError,
                        openai.RateLimitError) as ex:
                    openai_web_mention = "Visit https://platform.openai.com/docs/guides/error-codes/api-errors " \
                                         "for more details on how to resolve this error"
                    error_message, _ = self._generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request, '
                                             'I have notified your professor to look into the problem!')
                    openai_error_message = f"*** {type(ex).__name__} ***"
                    await self._report_error(f"{openai_error_message}\n{openai_web_mention}")
                    await self._report_error(error_message, True)
                    break

                except Exception as ex:
                    error_message, error_code = self._generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id,
                                             f'😵 **Error code {error_code}** 😵'
                                             f'\nAn unexpected error occurred. Please contact support.'
                                             f'\nError code for reference: {error_code}')
                    await self._report_error(error_message)
                    break

            # After while loop
            await self._send_message(thread_id, '*This conversation has been closed.*')

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
    async def _get_completion_with_retry(self, thread_id, engine, message_history):
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

    @staticmethod
    def _generate_error_message(guild_id, thread_id, ex):
        error_code = str(uuid.uuid4()).split('-')[0].upper()
        logging.exception('Error getting completion: ' + error_code)
        logging.exception('Error getting completion: ' + error_code)
        error_message = (
            f'😵 **Error code {error_code}** 😵'
            f'\nhttps://discord.com/channels/{guild_id}/{thread_id}'
            f'\n{ex}\n'
            '\n'.join(tb.format_exception(ex))
        )
        return error_message, error_code
