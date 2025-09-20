from ..armory.talk_tool import TalkTool
from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DuckContext, GPTMessage
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
        await self._ai_client.run_agent(context, self._main_agent, "Hi")

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
        self._talk_tool = talk_tool
        self._introduction = introduction

    async def __call__(self, context: DuckContext):
        duck_logger.info(f"Starting conversation with agent: {self._main_agent.name} (Thread: {context.thread_id})")
        message_history = []
        await self._talk_tool.send_message_to_user(context, self._introduction)
        while True:
            message = await self._talk_tool.receive_message_from_user(context)
            message_history.append(GPTMessage(role="user", content=message))
            await self._ai_client.run_agent(context, self._main_agent, "Hi")
