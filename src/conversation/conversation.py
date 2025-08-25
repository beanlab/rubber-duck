from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger


class AgentConversation:
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
