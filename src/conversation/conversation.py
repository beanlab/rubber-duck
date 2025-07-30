import asyncio

from quest import step, queue

from ..gen_ai.gen_ai import GPTMessage, RecordMessage, GenAIException, GenAIClient, Agent
from ..armory.armory import Armory
from ..utils.config_types import DuckContext, AgentMessage
from ..utils.logger import duck_logger
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


AGENT_NAME, AGENT_MESSAGE = str, str


class AgentConversation:
    def __init__(self,
                 name: str,
                 introduction: str,
                 ai_agent: Agent,
                 record_message: RecordMessage,
                 send_message: SendMessage,
                 add_reaction: AddReaction,
                 read_url,
                 wait_for_user_timeout,
                 armory: Armory,
                 file_size_limit: int,
                 file_type_ext: list[str] = None,
                 ):
        self.name = name

        self._introduction = introduction

        self._ai_agent = ai_agent

        self._record_message = step(record_message)

        self._send_message = step(send_message)
        self._add_reaction: AddReaction = step(add_reaction)
        self._read_url = step(read_url)

        self._wait_for_user_timeout = wait_for_user_timeout
        self._armory = armory
        self._file_size_limit = file_size_limit
        self._file_type_ext = file_type_ext or []


    @step
    async def _get_and_send_ai_response(
            self,
            context: DuckContext,
            user_message: str
    ) -> str:

        response: AgentMessage = await self._ai_agent.run(context, user_message)

        content= response.get("content")
        await self._send_message(context.thread_id, content)
        return content

    async def __call__(self, context: DuckContext):

        message_history = []

        duck_logger.info(f"Starting conversation with agent: {self._ai_agent.get_name()} (Thread: {context.thread_id})")

        introduction = self._introduction or "Hi, how can I help you?"
        await self._send_message(context.thread_id, introduction)

        async with queue('messages', None) as messages:
            while True:
                try:
                    try:
                        message: Message = await asyncio.wait_for(
                            messages.get(),
                            self._wait_for_user_timeout
                        )

                    except asyncio.TimeoutError:
                        break

                    if message['content']:
                        message_history.append(GPTMessage(role='user', content=message['content']))
                        await self._record_message(
                            context.guild_id, context.thread_id, context.author_id, message_history[-1]['role'],
                            message_history[-1]['content']
                        )

                    response = await self._get_and_send_ai_response(
                        context,
                        message["content"]
                    )

                    message_history.append(GPTMessage(role='assistant', content=response))

                except GenAIException:
                    await self._send_message(context.thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise
