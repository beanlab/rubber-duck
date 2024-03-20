import asyncio
import logging
import os
import uuid
import traceback as tb
from typing import TypedDict, Protocol, ContextManager
from openai import AsyncOpenAI
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
    # swapped
    file: list
    # is_file: bool

#create class attachment extends type dict and import to discord bot
class Attachment(TypedDict):
    attachment_id: int
    description: str
    filename: str

class GPTMessage(TypedDict):
    role: str
    content: str


class MessageHandler(Protocol):
    async def send_message(self, channel_id: int, message: str, file=None): ...

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
        self._typing = message_handler.typing

        self._metrics_handler = wrap_steps(metrics_handler)

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

                if len(message['file']) > 0:
                    await self._send_message(thread_id, "I'm sorry, I can't read file attachments. Please resend your message with the relevant parts of your file included in the message.")
                    continue

                message_history.append(GPTMessage(role='user', content=message['content']))

                # replaced by recommended lines (102-104) above line 106 (101 originally)
                # if message['is_file'] == True:
                #     appended_content = "*The user attached a file*"
                # else:
                #     appended_content = message['content']

                # message_history.append(GPTMessage(role='user', content=appended_content))

                user_id = message['author_id']
                guild_id = message['guild_id']

                await self._metrics_handler.record_message(
                    guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content'])

                try:
                    if message_history[-1]['content'] == "*The user attached a file*":
                        response = "I'm unable to read entire files directly. Could you please paste the relevant sections and rephrase your question? " \
                                   "This will help me assist you better!"

                        await self._metrics_handler.record_message(
                            guild_id, thread_id, user_id, 'assistant', response)

                    else:
                        choices, usage = await self._get_completion(thread_id, engine, message_history)
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
                    await self._report_error(error_message)

                    await self._send_message(thread_id,
                                             f'😵 **Error code {error_code}** 😵'
                                             f'\nAn error occurred.'
                                             f'\nPlease tell a TA or the instructor the error code.'
                                             '\n*This conversation is closed*')
                    return

    @step
    async def _get_completion(self, thread_id, engine, message_history) -> tuple[list, dict]:
        # Replaces _get_response
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
