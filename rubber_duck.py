import asyncio
import logging
import os
import traceback as tb
import uuid
from typing import TypedDict, Protocol, ContextManager

import openai
from openai import AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from quest import step, queue

from feedback import FeedbackWorkflow
from metrics import MetricsHandler

client = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])

AI_ENGINE = 'gpt-4'

V_SUPPORT_STATE_COMMAND = '2023-09-26 Support State'
V_LOG_ZIP_STATS = '2023-09-26 Zip log file, Stats'


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


class RubberDuckConfig(TypedDict):
    retry_protocol: RetryConfig


class BotCommandsConfig(TypedDict):
    command_channels: list[int]
    channels: list[ChannelConfig]
    defaults: ChannelConfig


class MessageHandler(Protocol):
    async def send_message(self, channel_id: int, message: str, file=None, view=None) -> int: ...

    async def edit_message(self, channel_id: int, message_id: int, new_content: str): ...

    async def report_error(self, msg: str, notify_admin: bool = False): ...

    def typing(self, channel_id: int) -> ContextManager: ...


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
                 message_handler: MessageHandler,
                 metrics_handler: MetricsHandler,
                 config: RubberDuckConfig,
                 workflow_manager
                 ):
        self._send_raw_message = message_handler.send_message
        self._send_message = step(message_handler.send_message)
        self._edit_message = step(message_handler.edit_message)
        self._report_error = step(message_handler.report_error)
        self._typing = message_handler.typing
        self._config = config
        self._metrics_handler = wrap_steps(metrics_handler)
        self._error_message_id = None
        self.workflow_manager = workflow_manager

        self.feedback_workflow = FeedbackWorkflow(
            metrics_handler.record_feedback,
            workflow_manager.send_event,
            message_handler.send_message
        )

    async def __call__(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
        return await self.have_conversation(thread_id, engine, prompt, initial_message, timeout)

    def generate_error_message(self, guild_id, thread_id, ex):
        error_code = str(uuid.uuid4()).split('-')[0].upper()
        logging.exception('Error getting completion: ' + error_code)
        error_message = (
            f'😵 **Error code {error_code}** 😵'
            f'\nhttps://discord.com/channels/{guild_id}/{thread_id}'
            f'\n{ex}\n'
            '\n'.join(tb.format_exception(ex))
        )
        return error_message, error_code

    #
    # Begin Conversation
    #
    async def have_conversation(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
        user_id = initial_message['author_id']

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
                    error_message, _ = self.generate_error_message(guild_id, thread_id, ex)
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
                    error_message, _ = self.generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request, '
                                             'I have notified your professor to look into the problem!')
                    openai_error_message = f"*** {type(ex).__name__} ***"
                    await self._report_error(f"{openai_error_message}\n{openai_web_mention}")
                    await self._report_error(error_message, True)
                    break

                except Exception as ex:
                    error_message, error_code = self.generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id,
                                             f'😵 **Error code {error_code}** 😵'
                                             f'\nAn unexpected error occurred. Please contact support.'
                                             f'\nError code for reference: {error_code}')
                    await self._report_error(error_message)
                    break

            # After while loop
            await self._send_message(thread_id, '*This conversation has been closed.*')
            await self.feedback_workflow.request_feedback(guild_id, thread_id, user_id)

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
        max_retries = self._config['retry_protocol']['max_retries']
        delay = self._config['retry_protocol']['delay']
        backoff = self._config['retry_protocol']['backoff']
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
