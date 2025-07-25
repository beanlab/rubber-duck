import asyncio

from openai.types.responses import ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput
from quest import step, queue

from ..gen_ai.gen_ai import GPTMessage, RecordMessage, GenAIException, GenAIClient
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
                 ai_agents: dict[str, GenAIClient],
                 starting_agent: str,
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
        self._ai_clients = ai_agents
        self._starting_agent = starting_agent
        self._agent_histories = {}


        self._record_message = step(record_message)

        self._send_message = step(send_message)
        self._add_reaction: AddReaction = step(add_reaction)
        self._read_url = step(read_url)

        self._wait_for_user_timeout = wait_for_user_timeout
        self._armory = armory
        self._file_size_limit = file_size_limit
        self._file_type_ext = file_type_ext or []

# Make a read function in discord bot that will read files.
    @step
    async def _get_and_send_ai_response(
            self,
            context: DuckContext,
            agent_name: str,
            message_history: list[GPTMessage | ResponseFunctionToolCallParam | FunctionCallOutput]
    ) -> tuple[AGENT_NAME, AGENT_MESSAGE]:

        duck_logger.debug(f"Processing with agent: {agent_name} (Thread: {context.thread_id})")

        response: AgentMessage = await self._ai_clients[agent_name].get_completion(
            context,
            message_history,
        )

        if file := response.get('file'):
            await self._send_message(context.thread_id, file=file)
            return agent_name, f"Sent file: {file['filename']}"

        if content := response.get('content'):
            if response['agent_name'] != agent_name:
                if response['agent_name'] not in self._agent_histories:
                    actual_agent = self._ai_clients[response['agent_name']].get_initial_agent()
                    self._agent_histories[response['agent_name']] = [
                        GPTMessage(role='system', content=actual_agent.instructions),
                        GPTMessage(role='user', content=content)
                    ]
                else:
                    self._agent_histories[response['agent_name']].append(
                        GPTMessage(role='user', content=content))
                return await self._get_and_send_ai_response(context, response['agent_name'], self._agent_histories[response['agent_name']])

            else:
                await self._send_message(context.thread_id, content)
                return response['agent_name'], content

        raise NotImplementedError(f'AI completion had neither content nor file.')

    async def __call__(self, context: DuckContext):

        agent_name = self._starting_agent

        duck_logger.info(f"Starting conversation with agent: {agent_name} (Thread: {context.thread_id})")

        introduction = self._introduction or "Hi, how can I help you?"
        await self._send_message(context.thread_id, introduction)

        async with queue('messages', None) as messages:
            while True:
                try:
                    if agent_name not in self._agent_histories:
                        actual_agent = self._ai_clients[agent_name].get_initial_agent()
                        self._agent_histories[agent_name] = [
                            GPTMessage(role='system', content=actual_agent.instructions)]
                    try:  # Timeout
                        message: Message = await asyncio.wait_for(
                            messages.get(),
                            self._wait_for_user_timeout
                        )

                    except asyncio.TimeoutError:
                        break

                    if message['content']:
                        self._agent_histories[agent_name].append(GPTMessage(role='user', content=message['content']))
                        await self._record_message(
                            context.guild_id, context.thread_id, context.author_id, self._agent_histories[agent_name][-1]['role'],
                            self._agent_histories[agent_name][-1]['content']
                        )

                    agent_name, response= await self._get_and_send_ai_response(
                        context,
                        agent_name,
                        self._agent_histories[agent_name]
                    )

                    self._agent_histories[agent_name].append(GPTMessage(role='assistant', content=response))

                except GenAIException:
                    await self._send_message(context.thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise
