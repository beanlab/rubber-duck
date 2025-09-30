from quest import step

from ..armory.talk_tool import TalkTool
from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger


class AgentLedConversation:
    def __init__(self,
                 name: str,
                 main_agent: Agent,
                 ai_client: AIClient,
                 ):
        self.name = name
        self._main_agent = main_agent
        self._ai_client = ai_client

    async def __call__(self, context: DuckContext):
        duck_logger.info(f"Starting conversation with agent: {self._main_agent.name} (Thread: {context.thread_id})")
        await self._ai_client.run_agent(context, self._main_agent, None)


class UserLedConversation:
    def __init__(self,
                 name: str,
                 main_agent: Agent,
                 ai_client: AIClient,
                 talk_tool: TalkTool,
                 introduction,
                 ):
        self.name = name

        self._main_agent = main_agent
        self._ai_client = ai_client
        self._get_message = step(talk_tool.receive_message_from_user)
        self._send_message = step(talk_tool.send_message_to_user)
        self._introduction = introduction

    async def __call__(self, context: DuckContext):
        duck_logger.info(f"Starting conversation with agent: {self._main_agent.name} (Thread: {context.thread_id})")
        await self._send_message(context, self._introduction)
        await self._ai_client.run_conversation(context, self._main_agent, self._get_message, self._send_message)



