import asyncio
import logging
import os
import uuid
import traceback as tb
from typing import TypedDict, Protocol, ContextManager
from openai import AsyncOpenAI
import openai
from openai.types.chat.chat_completion import ChatCompletion
from quest import step, queue

from metrics import MetricsHandler

client = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])

AI_ENGINE = 'gpt-4'
CONVERSATION_TIMEOUT = 60 * 3  # three minutes

V_SUPPORT_STATE_COMMAND = '2023-09-26 Support State'
V_LOG_ZIP_STATS = '2023-09-26 Zip log file, Stats'


class Message(TypedDict):
    guild_id: int
    channel_name: str
    channel_id: int
    author_id: int
    author_name: str
    author_mention: str
    message_id: int
    content: str


class GPTMessage(TypedDict):
    role: str
    content: str


class MessageHandler(Protocol):
    async def send_message(self, channel_id: int, message: str, file=None) -> int: ...

    async def edit_message(self, channel_id: int, message_id: int, new_content: str): ...

    def typing(self, channel_id: int) -> ContextManager: ...


class ErrorHandler(Protocol):
    async def __call__(self, message: str): ...


def wrap_steps(obj):
    for field in dir(obj):
        if field.startswith('_'):
            continue

        if callable(method := getattr(obj, field)):
            method = step(method)
            setattr(obj, field, method)

    return obj


class RubberDuck:
    def __init__(self,
                 error_handler: ErrorHandler,
                 message_handler: MessageHandler,
                 metrics_handler: MetricsHandler,
                 ):
        self._report_error = step(error_handler)
        self._send_raw_message = message_handler.send_message
        self._send_message = step(message_handler.send_message)
        self._edit_message = step(message_handler.edit_message)
        self._typing = message_handler.typing

        self._metrics_handler = wrap_steps(metrics_handler)
        self._error_message_id = None

    async def __call__(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
        return await self.have_conversation(thread_id, engine, prompt, initial_message, timeout)

    #
    # Begin Conversation
    #
    async def have_conversation(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
        async with queue('messages', str(thread_id)) as messages:
            message_history = [
                GPTMessage(role='system', content=prompt)
            ]
            user_id = initial_message['author_id']
            guild_id = initial_message['guild_id']
            await self._metrics_handler.record_message(
                guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])

            await self._send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

            while True:
                # TODO - if the conversation is getting long, and the user changes the subject
                #  prompt them to start a new conversation (and close this one)
                try:
                    message: Message = await asyncio.wait_for(messages.get(), timeout)

                except asyncio.TimeoutError:
                    await self._send_message(thread_id, '*This conversation has been closed.*')
                    return

                message_history.append(GPTMessage(role='user', content=message['content']))

                user_id = message['author_id']
                guild_id = message['guild_id']

                await self._metrics_handler.record_message(
                    guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content'])

                try:
                    choices, usage = await self._get_completion_with_retry(thread_id, engine, message_history)
                    response_message = choices[0]['message']
                    response = response_message['content'].strip()

                    await self._metrics_handler.record_usage(guild_id, thread_id, user_id,
                                                             engine,
                                                             usage['prompt_tokens'],
                                                             usage['completion_tokens'])

                    await self._metrics_handler.record_message(
                        guild_id, thread_id, user_id, response_message['role'], response_message['content'])

                    message_history.append(GPTMessage(role='assistant', content=response))

                    await self._send_message(thread_id, response)

                except Exception as ex:
                    error_code = str(uuid.uuid4()).split('-')[0].upper()
                    logging.exception('Error getting completion: ' + error_code)
                    error_message = (
                        f'😵 **Error code {error_code}** 😵'
                        f'\nhttps://discord.com/channels/{guild_id}/{thread_id}'
                        f'\n{ex}\n'
                        '\n'.join(tb.format_exception(ex))
                    )

                    # For server-side errors
                    if isinstance(ex,
                                  (openai.APITimeoutError, openai.InternalServerError, openai.UnprocessableEntityError)):
                        await self._edit_message(thread_id, self._error_message_id,
                                                 'I\'m having trouble connecting to the OpenAI servers, please open up a separate conversation and try again')
                    # For client-side errors
                    elif isinstance(ex, (openai.APIConnectionError, openai.BadRequestError,
                                         openai.AuthenticationError, openai.ConflictError, openai.ConflictError, openai.NotFoundError,
                                         openai.RateLimitError)):
                        user_ids_to_mention = [933123843038535741]
                        # user_ids_to_mention = [911012305880358952, 933123843038535741, 1014286006595358791, 353454081265762315, 941080292557471764] #Dr.Bean, MaKenna, Chase, YoungWoo, Molly's ID's
                        mentions = ' '.join([f'<@{user_id}>' for user_id in user_ids_to_mention])
                        openai_web_mention = "Visit https://platform.openai.com/docs/guides/error-codes/api-errors for more details on how to resolve this error"
                        await self._edit_message(thread_id, self._error_message_id,
                                                 'I\'m having trouble processing your request, I have notified your professor to look into the problem!')
                        if isinstance(ex, openai.APIConnectionError):
                            client_error_message = f"{mentions}\n*** APIConnectionError ***\n{openai_web_mention}"
                        elif isinstance(ex, openai.BadRequestError):
                            client_error_message = f"{mentions}\n*** BadRequestError ***\n{openai_web_mention}"
                        elif isinstance(ex, openai.AuthenticationError):
                            client_error_message = f"{mentions}\n*** AuthenticationError ***\n{openai_web_mention}"
                        elif isinstance(ex, openai.ConflictError):
                            client_error_message = f"{mentions}\n*** ConflictError ***\n{openai_web_mention}"
                        elif isinstance(ex, openai.NotFoundError):
                            client_error_message = f"{mentions}\n*** NotFoundError ***\n{openai_web_mention}"
                        elif isinstance(ex, openai.PermissionDeniedError):
                            client_error_message = f"{mentions}\n*** PermissionDeniedError ***\n{openai_web_mention}"
                        elif isinstance(ex, openai.RateLimitError):
                            client_error_message = f"{mentions}\n*** RateLimitError ***\n{openai_web_mention}"
                        await self._report_error(client_error_message)
                    else:
                        await self._edit_message(thread_id, self._error_message_id,
                                                 f'😵 **Error code {error_code}** 😵'
                                                 f'\nAn unexpected error occurred. Please contact support.'
                                                 f'\nError code for reference: {error_code}'
                                                 '\n*This conversation is closed*')

                    await self._report_error(error_message)

                    return

    @step
    async def _get_completion(self, thread_id, engine, message_history) -> tuple[list, dict]:
        # Replaces _get_response
        async with self._typing(thread_id):
            completion: ChatCompletion = await client.chat.completions.create(
                # model=engine,
                model = "fake_engine",
                messages=message_history
            )
            logging.debug(f"Completion: {completion}")
            completion_dict = completion.dict()
            choices = completion_dict['choices']
            usage = completion_dict['usage']
            return choices, usage

    @step
    async def _get_completion_with_retry(self, thread_id, engine, message_history):
        max_retries = 2
        delay = 2
        backoff = 2
        retries = 0
        current_delay = delay
        processing_message_sent = False
        while retries < max_retries:
            try:
                return await self._get_completion(thread_id, engine, message_history)
            except Exception as ex:
                print("This is the exception: ", ex)
                if not processing_message_sent:
                    processing_message_id = await self._send_message(thread_id, 'Trying to contact servers...')
                    self._error_message_id = processing_message_id
                    processing_message_sent = True
                retries += 1
                # These errors are specific to the client side of things, so we don't need to send multiple calls to the server
                if retries >= max_retries or isinstance(ex, (openai.APIConnectionError, openai.BadRequestError,
                                         openai.AuthenticationError, openai.ConflictError, openai.ConflictError, openai.NotFoundError,
                                         openai.RateLimitError)):
                    raise
                logging.warning(
                    f"Retrying due to {ex}, attempt {retries}/{max_retries}. Waiting {current_delay} seconds.")
                await asyncio.sleep(current_delay)
                current_delay *= backoff