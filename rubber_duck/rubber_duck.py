import asyncio
import logging
import os
import traceback as tb
import uuid
from pathlib import Path
from typing import TypedDict, Protocol, ContextManager, TypeVar

import openai
from openai import AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from quest import step, queue, alias

from metrics import MetricsHandler

client = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])


class Attachment(TypedDict):
    attachment_id: int
    description: str
    filename: str


class Message(TypedDict):
    guild_id: int
    channel_name: str
    channel_id: int
    author_id: int
    author_name: str
    author_mention: str
    message_id: int
    content: str
    file: list[Attachment]


class GPTMessage(TypedDict):
    role: str
    content: str


class ChannelConfig(TypedDict):
    name: str | None
    id: int | None
    prompt: str | None
    prompt_file: str | None
    engine: str | None
    timeout: int | None


class RetryConfig(TypedDict):
    max_retries: int
    delay: int
    backoff: int


class DuckConfig(TypedDict):
    defaults: ChannelConfig
    channels: list[ChannelConfig]


class MessageHandler(Protocol):
    async def send_message(self, channel_id: int, message: str, file=None, view=None) -> int: ...

    async def edit_message(self, channel_id: int, message_id: int, new_content: str): ...

    async def report_error(self, msg: str, notify_admin: bool = False): ...

    def typing(self, channel_id: int) -> ContextManager: ...

    async def create_thread(self, parent_channel_id: int, title: str) -> int: ...


class _Wrapped:
    pass


T = TypeVar('T')


def wrap_steps(obj: T) -> T:
    wrapped = _Wrapped()

    for field in dir(obj):
        if field.startswith('_'):
            continue

        if callable(method := getattr(obj, field)):
            method = step(method)
            setattr(wrapped, field, method)

    return wrapped


def generate_error_message(guild_id, thread_id, ex):
    error_code = str(uuid.uuid4()).split('-')[0].upper()
    logging.exception('Error getting completion: ' + error_code)
    error_message = (
        f'😵 **Error code {error_code}** 😵'
        f'\nhttps://discord.com/channels/{guild_id}/{thread_id}'
        f'\n{ex}\n'
        '\n'.join(tb.format_exception(ex))
    )
    return error_message, error_code


class RubberDuck:
    def __init__(self,
                 message_handler: MessageHandler,
                 metrics_handler: MetricsHandler,
                 duck_config: DuckConfig,
                 retry_config: RetryConfig,
                 start_feedback_workflow
                 ):
        self._send_raw_message = message_handler.send_message
        self._send_message = step(message_handler.send_message)
        self._edit_message = step(message_handler.edit_message)
        self._report_error = step(message_handler.report_error)
        self._create_thread = step(message_handler.create_thread)
        self._typing = message_handler.typing

        self._channel_configs = {config['name']: config for config in duck_config['channels']}
        self._default_config = duck_config['defaults']
        self._retry_config = retry_config
        self._metrics_handler = metrics_handler
        # self._metrics_handler.record_message = step(self._metrics_handler.record_message)
        # self._metrics_handler.record_feedback = step(self._metrics_handler.record_feedback)
        # self._metrics_handler.record_usage = step(self._metrics_handler.record_usage)
        self._error_message_id = None

        self.start_feedback_workflow = step(start_feedback_workflow)

    async def __call__(self, channel_name: str, initial_message: Message, timeout=600):
        prompt, engine, timeout = self._get_channel_settings(channel_name, initial_message)

        thread_id = await self._setup_thread(initial_message)

        async with alias(str(thread_id)):
            await self._have_conversation(thread_id, engine, prompt, initial_message, timeout)

    #
    # Begin Conversation
    #
    def _get_channel_settings(self, channel_name: str, initial_message: Message):
        channel_config = self._channel_configs[channel_name]

        prompt = channel_config.get('prompt', None)
        if prompt is None:
            prompt_file = channel_config.get('prompt_file', None)
            if prompt_file is None:
                prompt = initial_message['content']
            else:
                prompt = Path(prompt_file).read_text()

        engine = channel_config.get('engine', self._default_config['engine'])

        timeout = channel_config.get('timeout', self._default_config['timeout'])

        return prompt, engine, timeout

    @step
    async def _setup_thread(self, initial_message: Message):

        thread_id = await self._create_thread(
            initial_message['channel_id'],
            initial_message['content'][:20]
        )

        # Send welcome message to add the user to the thread
        await self._send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

        # Notify the user in the original channel of the new thread
        await self._send_message(
            initial_message['channel_id'],
            f"<@{initial_message['author_id']}> Click here to join the conversation: <#{thread_id}>"
        )

        return thread_id

    @step
    async def _have_conversation(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):

        async with queue('messages', None) as messages:
            message_history = [
                GPTMessage(role='developer', content=prompt)
            ]

            user_id = initial_message['author_id']
            guild_id = initial_message['guild_id']

            # Record the prompt
            await self._metrics_handler.record_message(
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

                    await self._metrics_handler.record_message(
                        guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content']
                    )

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

                except (openai.APITimeoutError, openai.InternalServerError, openai.UnprocessableEntityError) as ex:
                    error_message, _ = generate_error_message(guild_id, thread_id, ex)
                    await self._edit_message(thread_id, self._error_message_id,
                                             'I\'m having trouble connecting to the OpenAI servers, '
                                             'please open up a separate conversation and try again')
                    await self._report_error(error_message)
                    break

                except (openai.APIConnectionError, openai.BadRequestError,
                        openai.AuthenticationError, openai.ConflictError, openai.NotFoundError,
                        openai.RateLimitError) as ex:
                    openai_web_mention = "Visit https://platform.openai.com/docs/guides/error-codes/api-errors " \
                                         "for more details on how to resolve this error"
                    error_message, _ = generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request, '
                                             'I have notified your professor to look into the problem!')
                    openai_error_message = f"*** {type(ex).__name__} ***"
                    await self._report_error(f"{openai_error_message}\n{openai_web_mention}")
                    await self._report_error(error_message, True)
                    break

                except Exception as ex:
                    error_message, error_code = generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id,
                                             f'😵 **Error code {error_code}** 😵'
                                             f'\nAn unexpected error occurred. Please contact support.'
                                             f'\nError code for reference: {error_code}')
                    await self._report_error(error_message)
                    break

            # After while loop
            await self._send_message(thread_id, '*This conversation has been closed.*')
            await self.start_feedback_workflow("rubber-duck", guild_id, thread_id, user_id)

    @step
    async def _get_completion(self, thread_id, engine, message_history) -> tuple[list, dict]:
        async with self._typing(thread_id):
            completion: ChatCompletion = await client.chat.completions.create(
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
                    processing_message_id = await self._send_message(thread_id, 'Trying to contact servers...')
                    self._error_message_id = processing_message_id
                retries += 1
                if retries >= max_retries:
                    raise

                logging.warning(
                    f"Retrying due to {ex}, attempt {retries}/{max_retries}. Waiting {delay} seconds.")
                await asyncio.sleep(delay)
                delay *= backoff
