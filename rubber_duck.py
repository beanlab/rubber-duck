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

        async with queue('messages', str(thread_id)) as messages:
            message_history = [
                GPTMessage(role='system', content=prompt)
            ]
            track_summarization_index = 0
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
                    await self.feedback_workflow.request_feedback(guild_id, thread_id, user_id)
                    return

                message_history.append(GPTMessage(role='user', content=message['content']))
                track_summarization_index += 1

                user_id = message['author_id']
                guild_id = message['guild_id']

                await self._metrics_handler.record_message(
                    guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content'])

                # message_history = self.reduce_history(message_history)

                try:
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
                
                    if track_summarization_index % 3 == 0:
                        summary = await self.summarize_message_history(thread_id, engine, message_history)
                        message_history = [message_history[0], GPTMessage(role='system', content=summary)]

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
    # def reduce_history(self, message_history):
    #     if len(message_history) > 4:
    #         return [message_history[0]] + message_history[-4:]
    #     return message_history

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

    @step
    async def summarize_message_history(self, thread_id, engine, message_history):
        conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in message_history])

        prompt = (
            "Summarize:\n"
            "- The latest version of the student's code (if any).\n"
            "- The latest examples provided by the AI (if any).\n"
            "- A bullet list of the key details from the conversation, focusing on what the student needs to understand and their main questions.\n"
            "Transcript:\n"
            f"{conversation_text}"
        )

        async with self._typing(thread_id):
            try:
                completion = await client.chat.completions.create(
                    model=engine,
                    prompt=prompt,
                    max_tokens=700
                )
                logging.debug(f"Completion: {completion}")
                summarized_text = completion.choices[0].text.strip()
                return summarized_text
            except Exception as e:
                logging.error(f"Error while summarizing: {e}")
                return "Error in generating summary."