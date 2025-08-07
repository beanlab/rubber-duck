from pathlib import Path

from .gen_ai import RecordMessage, Agent, AIClient
from ..armory.armory import Armory
from ..armory.data_store import DataStore
from ..armory.stat_tools import StatsTools
from ..armory.talk_tool import TalkTool
from ..conversation.conversation import AgentConversation
from ..duck_orchestrator import DuckConversation
from ..utils.config_types import AgentConversationSettings, SingleAgentSettings, Config, DuckContext
from ..utils.logger import duck_logger

def _build_agent(
        config: SingleAgentSettings
) -> Agent:
    prompt = config.get('prompt', None)
    if not prompt:
        prompt_files = config.get("prompt_files")
        if not prompt_files:
            raise ValueError(f"You must provide either 'prompt' or 'prompt_files' for {config['name']}")

        prompt = f'\n'.join([Path(prompt_path).read_text(encoding="utf-8") for prompt_path in prompt_files])

    tool_required = config.get("tool_required", "auto")
    if tool_required not in ["auto", "required", "none"]:
        tool_required = {"type": "function", "name": tool_required}

    goal_config = config.get("goal", None)
    if goal_config:
        goal = goal_config["description"]
    else:
        goal = None
    agent = Agent(
        name=config["name"],
        description=config.get("description", None),
        prompt=prompt,
        model=config["engine"],
        tools=config["tools"],
        tool_settings=tool_required,
        goal=goal
    )
    return agent


def _build_main_agent(
        agent_settings: SingleAgentSettings,
        agent_tool_settings: list[SingleAgentSettings] | None,
        armory: Armory,
        client: AIClient
) -> Agent:
    main_agent = _build_agent(agent_settings)

    if agent_tool_settings:
        for agent_settings in agent_tool_settings:
            agent = _build_agent(agent_settings)
            armory.add_tool(client.build_agent_tool(agent))
            if goal_config := agent_settings.get("goal", None):
                _armory.add_tool(client.build_goal_accomplished_tool(agent, goal_config['name']))
    return main_agent


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

def _add_agent_tools(config: Config, client: AIClient) -> None:
    for agent_settings in config['agents_as_tools']:
        agent = _build_agent(agent_settings)
        _armory.add_tool(client.build_agent_tool(agent))
        if goal_config := agent_settings.get("goal", None):
            _armory.add_tool(client.build_goal_accomplished_tool(agent, goal_config['name']))


def build_agent_conversation_duck(
        name: str,
        config: Config,
        settings: AgentConversationSettings,
        record_message: RecordMessage,
        bot,
) -> DuckConversation:
    armory = _get_armory(config, bot, record_message)
    ai_client = AIClient(armory)
    _add_agent_tools(config, ai_client)
    starting_agent = _build_main_agent(settings['agent'], settings.get('agents_as_tools', None), armory, ai_client)

    agent_conversation = AgentConversation(
        name,
        starting_agent,
        ai_client,
    )

    return agent_conversation
