import asyncio
import logging
import traceback as tb
import uuid
from pathlib import Path
from typing import TypedDict, Protocol

from quest import step, queue, wrap_steps

from metrics.feedback import GetConvoFeedback
from metrics.feedback_manager import FeedbackManager
from utils.protocols import Message, SendMessage, ReportError, IndicateTyping


class RetryableException(Exception):
    def __init__(self, exception, message):
        self.exception = exception
        self.message = message
        super().__init__(self.exception.__str__())


class GenAIException(Exception):
    def __init__(self, exception, web_mention):
        self.exception = exception
        self.web_mention = web_mention
        super().__init__(self.exception.__str__())


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


class GenAIClient(Protocol):
    async def get_completion(self, engine, message_history) -> tuple[list, dict]: ...


class RetryableGenAIClient(Protocol):
    async def get_completion(self, guild_id: int, thread_id: int, engine: str, message_history: list[GPTMessage]) -> \
    tuple[list, dict]: ...

class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, engine: str, message_history: list[GPTMessage], timeout: int = 600): ...


def generate_error_message(guild_id, thread_id, ex):
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



class BasicSetupConversation:
    def __init__(self, record_message):
        self._record_message = step(record_message)

    async def __call__(self, thread_id: int, prompt: str, initial_message: Message) -> list[GPTMessage]:
        message_history = [GPTMessage(role='system', content=prompt)]
        user_id = initial_message['author_id']
        guild_id = initial_message['guild_id']

        await self._record_message(
            guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])
        return message_history


class HaveStandardGptConversation:
    def __init__(self,
                 ai_client: RetryableGenAIClient,
                 record_message: RecordMessage,
                 record_usage: RecordUsage,
                 send_message: SendMessage,
                 report_error: ReportError,
                 typing: IndicateTyping,
                 retry_config: RetryConfig,
                 setup_conversation: BasicSetupConversation
                 ):
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._ai_client = ai_client
        wrap_steps(self._ai_client, ['get_completion'])
        self._typing = typing
        self._retry_config = retry_config
        self._setup_conversation = step(setup_conversation)

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):

        prompt_file = settings["prompt_file"]
        if prompt_file:
            prompt = Path(prompt_file).read_text(encoding="utf-8")
        else:
            prompt = initial_message['content']

        # Get engine and timeout from duck settings, falling back to defaults if not set
        engine = settings["engine"]
        timeout = settings["timeout"]

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)


        async with queue('messages', None) as messages:
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

                    choices, usage = await self._ai_client.get_completion(guild_id, thread_id, engine, message_history)

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

                except GenAIException as ex:
                    web_mention = ex.web_mention
                    error_message, _ = generate_error_message(guild_id, thread_id, ex)
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request, '
                                             'I have notified your professor to look into the problem!')
                    genai_error_message = f"*** {type(ex).__name__} ***"
                    await self._report_error(f"{genai_error_message}\n{web_mention}")
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


class HaveTAGradingConversation:
    def __init__(self,
                 record_message: RecordMessage,
                 send_message: SendMessage,
                 report_error: ReportError,
                 typing: IndicateTyping,
                 feedback_manager: FeedbackManager
                 ):
        self._record_message = step(record_message)
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._typing = typing
        self._feedback_manager = feedback_manager

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):


        channel_to_review = settings["channel_to_review"]
        timeout = settings["timeout"]
        message_history = []

        async with queue('messages', None) as messages:
            await self._send_message(
                thread_id,
                "Please only use the valid commands listed below.\n"
                "/help (To get more information on how this channel works)\n"
                "/next (To get the next conversation link that requires feedback)\n"
            )
            while True:
                try:
                    message: Message = await asyncio.wait_for(messages.get(), timeout)
                    user_input = message['content'].strip()

                    if user_input.startswith('/'):
                        if user_input == '/help':
                            await self._send_message(thread_id, 'Help message')
                            continue

                        elif user_input == '/next':
                            conversation_link = await self._feedback_manager.get_conversation(channel_to_review)
                            if not conversation_link:
                                await self._send_message(thread_id, "No more conversations to review.")
                                continue

                            await self._send_message(thread_id, conversation_link)

                            message_history.append(GPTMessage(role='user', content=user_input))
                            message_history.append(GPTMessage(role='assistant', content=conversation_link))

                            await self._record_message(
                                message['guild_id'],
                                thread_id,
                                message['author_id'],
                                'user',
                                user_input
                            )

                            await self._record_message(
                                message['guild_id'],
                                thread_id,
                                message['author_id'],
                                'assistant',
                                conversation_link
                            )
                            continue

                        else:
                            await self._send_message(thread_id,
                                "Not a valid command. Please use /help or /next.\n")
                            continue

                    else:
                        await self._send_message(thread_id,
                            "Please only use the valid commands listed below.\n"
                            "/help (To get more information on how this channel works)\n"
                            "/next (To get the next conversation link that requires feedback)"
                        )

                except asyncio.TimeoutError:
                    await self._send_message(thread_id, "*This conversation has timed out.*")
                    break

                except Exception as ex:
                    error_message, error_code = generate_error_message(message.get('guild_id', 0), thread_id, ex)
                    await self._send_message(thread_id,
                        f'😵 **Error code {error_code}** 😵\n'
                        f'An unexpected error occurred. Please contact support.\n'
                        f'Error code for reference: {error_code}')
                    await self._report_error(error_message)
                    break