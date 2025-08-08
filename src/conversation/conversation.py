from ..gen_ai.gen_ai import GPTMessage, Agent, AIClient
from ..utils.config_types import DuckContext, HistoryType
from ..utils.logger import duck_logger


AGENT_NAME, AGENT_MESSAGE = str, str


class AgentConversation:
    def __init__(self,
                 name: str,
                 starting_agent: Agent,
                 ai_client: AIClient,
                 ):
        self.name = name
        self._starting_agent = starting_agent
        self._ai_client = ai_client

    async def __call__(self, context: DuckContext):
        duck_logger.info(f"Starting conversation with agent: {self._starting_agent.name} (Thread: {context.thread_id})")
        await self._ai_client.run_agent(context, self._starting_agent, "Hi")