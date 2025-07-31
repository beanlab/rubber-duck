from pathlib import Path

from .gen_ai import RecordMessage, Agent
from ..armory.armory import Armory
from ..armory.data_store import DataStore
from ..armory.stat_tools import StatsTools
from ..armory.talk_tool import TalkTool
from ..conversation.conversation import AgentConversation
from ..duck_orchestrator import DuckConversation
from ..utils.config_types import AgentConversationSettings, SingleAgentSettings, Config
from ..utils.logger import duck_logger


def _build_agent(
        config: SingleAgentSettings,
        armory: Armory
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
        tools=[tool for tool in config["tools"] if not tool.startswith("run_")],
        model=config["engine"],
        armory=armory,
        max_iterations=config.get('max_iterations', 10),
    )
    armory.scrub_agent(agent)
    return agent

def _build_agents(
        settings: list[SingleAgentSettings],
        armory: Armory,
        starting_agent: str
) -> Agent:
    agents = {}

    for agent_settings in settings:
        agent = _build_agent(agent_settings, armory)
        agents[agent_settings['name']] = agent

    for agent_settings in settings:
        agent = agents[agent_settings['name']]
        handoffs = [tool for tool in agent_settings.get('tools', []) if tool.startswith("run_")]
        for handoff in handoffs:
            agent.add_tool(handoff)
    return agents[starting_agent]


# noinspection PyTypeChecker
_armory: Armory = None


def _get_armory(config: Config, send_message) -> Armory:
    global _armory
    if _armory is None:
        _armory = Armory(send_message)

        if 'dataset_folder_locations' in config:
            data_store = DataStore(config['dataset_folder_locations'])
            stat_tools = StatsTools(data_store)
            _armory.scrub_tools(stat_tools)
        else:
            duck_logger.warning("**No dataset folder locations provided in config**")

        talk_tool = TalkTool(send_message, 30)
        _armory.scrub_tools(talk_tool)

    return _armory


def build_agent_conversation_duck(
        name: str,
        config: Config,
        settings: AgentConversationSettings,
        record_message: RecordMessage,
        bot,
) -> DuckConversation:
    armory = _get_armory(config, bot.send_message)
    starting_agent = settings.get('starting_agent')
    start = _build_agents(settings['agents'], armory, starting_agent)

    agent_conversation = AgentConversation(
        name,
        settings.get('introduction'),
        start,
        record_message,
        bot.send_message,
        bot.add_reaction,
        bot.read_url,
        settings.get('timeout', 60 * 5),
        armory,
        settings.get('file_size_limit', 0),
        settings.get('file_type_ext', []),
    )

    return agent_conversation
