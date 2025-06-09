import asyncio
from typing import Protocol

from quest import step, queue, wrap_steps

from ..armory.armory import Armory
from ..utils.config_types import DuckContext
from ..utils.gen_ai import GPTMessage, RecordMessage, GenAIException, Sendable, GenAIClient
from ..utils.protocols import Message, SendMessage, ReportError, AddReaction


class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, engine: str, message_history: list[GPTMessage], timeout: int = 600): ...


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


class AgentSetupConversation:
    def __init__(self, record_message):
        self._record_message = step(record_message)

    async def __call__(self, thread_id: int, initial_message: Message) -> list[GPTMessage]:
        message_history = [GPTMessage(role='system',
                                      content="Introduce yourself and what you can do to the user using the talk_to_user tool"),
                           GPTMessage(role='user', content="Hi")]
        user_id = initial_message['author_id']
        guild_id = initial_message['guild_id']

        await self._record_message(
            guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])
        await self._record_message(
            guild_id, thread_id, user_id, message_history[1]['role'], message_history[1]['content'])
        return message_history


class AgentConversation:
    def __init__(self,
                 name: str,
                 ai_agent: GenAIClient,
                 record_message: RecordMessage,
                 send_message: SendMessage,
                 report_error: ReportError,
                 add_reaction: AddReaction,
                 wait_for_user_timeout,
                 armory: Armory
                 ):
        self.name = name
        self._ai_client = wrap_steps(ai_agent, ['get_completion'])

        self._record_message = step(record_message)

        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._add_reaction: AddReaction = step(add_reaction)

        self._wait_for_user_timeout = wait_for_user_timeout
        self._armory = armory

    async def __call__(self, context: DuckContext):

        if 'duck' in context.content:
            await self._add_reaction(context.channel_id, context.message_id, "🦆")

        message_history = []

        introduction = self._ai_client.introduction or "Hi, how can I help you?"
        await self._send_message(context.thread_id, introduction)

        async with queue('messages', None) as messages:
            while True:
                try:  # catch all errors
                    try:
                        # Waiting for a response from the user
                        message: Message = await asyncio.wait_for(messages.get(), self._wait_for_user_timeout)

                    except asyncio.TimeoutError:
                        break

                    if len(message['file']) > 0:
                        await self._send_message(
                            context.thread_id,
                            "I'm sorry, I can't read file attachments. "
                            "Please resend your message with the relevant parts of your file included in the message."
                        )
                        continue

                    message_history.append(GPTMessage(role='user', content=message['content']))

                    await self._record_message(
                        context.guild_id, context.thread_id, context.author_id, message_history[-1]['role'],
                        message_history[-1]['content']
                    )

                    response = await self._ai_client.get_completion(
                        context,
                        message_history,
                    )

                    await self._send_message(context.thread_id, response)

                except GenAIException:
                    await self._send_message(context.thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise
