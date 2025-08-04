from pathlib import Path

from .gen_ai import RecordMessage, Agent, AIClient
from ..armory.armory import Armory
from ..armory.data_store import DataStore
from ..armory.stat_tools import StatsTools
from ..armory.talk_tool import TalkTool
from ..conversation.conversation import AgentConversation
from ..duck_orchestrator import DuckConversation
from ..utils.config_types import AgentConversationSettings, SingleAgentSettings, Config, DuckContext, HistoryType
from ..utils.logger import duck_logger

def build_agent_handoff_tool(agent_instance: Agent, client: AIClient):
    name = agent_instance.name
    description = agent_instance.description

    async def agent_runner(ctx: DuckContext, history: list[HistoryType]):
        duck_logger.debug(f"Handoff to agent: {name}")
        return await client.run_agent(ctx, history, agent_instance)

    function_name = f"{name}"
    agent_runner.__name__ = function_name
    agent_runner.__doc__ = description
    return agent_runner


def _build_agent(
        config: SingleAgentSettings,
        armory: Armory,
        ai_client: AIClient,

) -> Agent:
    prompt = config.get('prompt')
    if not prompt:
        prompt_files = config.get("prompt_files")
        if not prompt_files:
            raise ValueError(f"You must provide either 'prompt' or 'prompt_files' for {config['name']}")

        prompt = f'\n'.join([Path(prompt_path).read_text(encoding="utf-8") for prompt_path in prompt_files])

    agent = Agent(
        name=config["name"],
        description=config["description"],
        prompt=prompt,
        model=config["engine"],
        tools=config["tools"]
    )

    armory.add_tool(build_agent_handoff_tool(agent, ai_client))
    return agent


def _build_agents(
        settings: list[SingleAgentSettings],
        armory: Armory,
        starting_agent: str,
        ai_client: AIClient
) -> Agent:
    agents = {}

    for agent_settings in settings:
        agent = _build_agent(agent_settings, armory, ai_client)
        agents[agent_settings['name']] = agent

    return agents[starting_agent]


# noinspection PyTypeChecker
_armory: Armory = None


def _get_armory(config: Config, bot, record_message) -> Armory:
    global _armory
    if _armory is None:
        _armory = Armory()

        if 'dataset_folder_locations' in config:
            data_store = DataStore(config['dataset_folder_locations'])
            stat_tools = StatsTools(data_store)
            _armory.scrub_tools(stat_tools)
        else:
            duck_logger.warning("**No dataset folder locations provided in config**")

        talk_tool = TalkTool(bot.send_message, record_message, 30)
        _armory.scrub_tools(talk_tool)

    return _armory


def build_agent_conversation_duck(
        name: str,
        config: Config,
        settings: AgentConversationSettings,
        record_message: RecordMessage,
        bot,
) -> DuckConversation:
    armory = _get_armory(config, bot, record_message)
    ai_client = AIClient(armory)
    starting= settings.get('starting_agent')
    starting_agent = _build_agents(settings['agents'], armory, starting, ai_client)

    agent_conversation = AgentConversation(
        name,
        starting_agent,
        ai_client,
    )

    return agent_conversation
