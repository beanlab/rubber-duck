from ..armory.talk_tool import TalkTool
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


class DiscordAgentConversation:
    def __init__(self,
                 name: str,
                 main_agent: Agent,
                 ai_client: AIClient,
                 talk_tool: TalkTool
                 ):
        self.name = name
        self._main_agent = main_agent
        self._ai_client = ai_client
        self._talk_tool = talk_tool

    async def __call__(self, context: DuckContext):
        await self._talk_tool.send_message_to_user(context, "What is the guild id of the new server?")
        guild = await self._talk_tool.receive_message_from_user(context)
        await self._talk_tool.send_message_to_user(context, "This bot requires you to accept the bot into the newly created server.\n The link to the bot is https://discord.com/oauth2/authorize?client_id=1329497251265122344&permissions=126000&scope=bot\n Paste the link into the general channel and authorize it in the server.\n Once you have done this, please type 'done' to continue.")
        response = await self._talk_tool.receive_message_from_user(context)
        if "done" not in response.lower():
            await self._talk_tool.send_message_to_user(context, "You did not type 'done'. Exiting.")
            return
        else:
            await self._ai_client.run_agent(context, self._main_agent, f"Hi, my guild_id is: {guild}")




