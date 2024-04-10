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

from feedback import FeedbackWorkflow

client = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])

AI_ENGINE = 'gpt-4'

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
    async def send_message(self, channel_id: int, message: str, file=None, view=None): ...

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
                 workflow_manager
                 ):
        self._report_error = step(error_handler)
        self._send_raw_message = message_handler.send_message
        self._send_message = step(message_handler.send_message)
        self._typing = message_handler.typing

        self._metrics_handler = wrap_steps(metrics_handler)

        self.workflow_manager = workflow_manager

        async def post_event(workflow_id, name, identity, action, *args):
            await workflow_manager.send_event(workflow_id, name, identity, action, *args)

        self.feedback_workflow = FeedbackWorkflow(metrics_handler.record_feedback, post_event, message_handler.send_message)

    async def __call__(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
        return await self.have_conversation(thread_id, engine, prompt, initial_message, timeout)
    
    
    #
    # Begin Conversation
    #
    async def have_conversation(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
        user_id = initial_message['author_id']
        long_input_char = 100

        async with queue('messages', str(thread_id)) as messages:
            message_history = {
                0: GPTMessage(role='system', content=prompt)
            }

            user_id = initial_message['author_id']
            guild_id = initial_message['guild_id']
            await self._metrics_handler.record_message(
                guild_id, thread_id, user_id, 0, message_history[0]['role'], message_history[0]['content'])

            await self._send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

            latest_long_input_index = None
            message_index = 1

            while True:
                # TODO - if the conversation is getting long, and the user changes the subject
                #  prompt them to start a new conversation (and close this one)
                try:
                    message: Message = await asyncio.wait_for(messages.get(), timeout)

                except asyncio.TimeoutError:
                    await self._send_message(thread_id, '*This conversation has been closed.*')
                    await self.feedback_workflow.request_feedback(guild_id, thread_id, user_id)
                    return

                message_history[message_index] = GPTMessage(role='user', content=message['content'])

                if len(message['content']) > long_input_char:
                    latest_long_input_index = message_index

                # Message used for response
                response_used_messages = {0: message_history[0]}
                if latest_long_input_index:
                    response_used_messages[latest_long_input_index] = message_history[latest_long_input_index]  # If there is a user input that is longer than somewhat characters assume it as a code, put that into the response_used_messages assuming it is a code. If user submits an input that is longer than somewhat character one more time, replace it.

                response_used_messages.update({i: message_history[i] for i in sorted(message_history.keys())[-3:]}) # Last 9 messages
                response_used_messages = {key: response_used_messages[key] for key in sorted(response_used_messages.keys())}

                user_id = message['author_id']
                guild_id = message['guild_id']

                await self._metrics_handler.record_message(
                    guild_id, thread_id, user_id, message_index, message_history[message_index]['role'], message_history[message_index]['content'])

                message_index += 1

                message_history = self.reduce_history(message_history)

                try:
                    choices, usage = await self._get_completion(thread_id, engine, list(response_used_messages.values()))
                    response_message = choices[0]['message']
                    response = response_message['content'].strip()

                    await self._metrics_handler.record_usage(guild_id, thread_id, user_id,
                                                             engine,
                                                             usage['prompt_tokens'],
                                                             usage['completion_tokens'])

                    await self._metrics_handler.record_message(
                        guild_id, thread_id, user_id, message_index, response_message['role'], response_message['content'])

                    message_history[message_index] = GPTMessage(role='assistant', content=response)
                    message_index += 1

                    await self._send_message(thread_id, response)

                    print(f"response used messages: {response_used_messages}")

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
    
    # Keep message 0 for instruction and the last 20 messages
    def reduce_history(self, message_history):
        if len(message_history) > 20:
            return [message_history[0]] + message_history[-20:]
        return message_history

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

# async def _summarize
# make a recent_messages = [] and append that to message_history -> message_history.append(GPTMessage(role='system', content=summary))