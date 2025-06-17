import asyncio

from quest import step, queue

from .message_context import generate_message_history_from_message_context
from ..agents.gen_ai import GPTMessage, RecordMessage, GenAIException, GenAIClient
from ..armory.armory import Armory
from ..utils.config_types import DuckContext, AgentMessage
from ..utils.protocols import Message, SendMessage, AddReaction


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

AGENT_NAME, AGENT_MESSAGE = str, str


class AgentConversation:
    def __init__(self,
                 name: str,
                 introduction: str,
                 ai_agents: dict[str, GenAIClient],
                 starting_agent: str,
                 record_message: RecordMessage,
                 send_message: SendMessage,
                 add_reaction: AddReaction,
                 wait_for_user_timeout,
                 armory: Armory,
                 message_context: list[str],
    ):
        self.name = name

        self._introduction = introduction
        self._ai_clients = ai_agents
        self._starting_agent = starting_agent

        self._record_message = step(record_message)

        self._send_message = step(send_message)
        self._add_reaction: AddReaction = step(add_reaction)

        self._wait_for_user_timeout = wait_for_user_timeout
        self._armory = armory

        self._message_context = message_context

    @step
    async def _get_and_send_ai_response(
            self,
            context: DuckContext,
            agent_name: str,
            message_history: list[GPTMessage]
    ) -> tuple[AGENT_NAME, AGENT_MESSAGE]:

        response: AgentMessage = await self._ai_clients[agent_name].get_completion(
            context,
            message_history,
        )

        if file := response.get('file'):
            await self._send_message(context.thread_id, file=file)
            return file['filename']

        if content := response.get('content'):
            await self._send_message(context.thread_id, content)
            return response['agent_name'], content

        raise NotImplementedError(f'AI completion had neither content nor file.')

    async def __call__(self, context: DuckContext):

        agent_name = self._starting_agent
        message_history = generate_message_history_from_message_context(self._message_context[:])

        introduction = self._introduction or "Hi, how can I help you?"
        await self._send_message(context.thread_id, introduction)

        async with queue('messages', None) as messages:
            while True:
                try:  # catch GenAIException
                    try:  # Timeout
                        message: Message = await asyncio.wait_for(
                            messages.get(),
                            self._wait_for_user_timeout
                        )

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

                    agent_name, response = await self._get_and_send_ai_response(
                        context,
                        agent_name,
                        message_history
                    )

                    message_history.append(GPTMessage(role='assistant', content=response))

                except GenAIException:
                    await self._send_message(context.thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise
