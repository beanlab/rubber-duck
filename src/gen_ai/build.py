from pathlib import Path
from typing import Iterable

from .agent import Agent
from .coordinator import AgentCoordinator
from .gen_ai import AgentClient, RetryableGenAI, RecordMessage
from .tools import ToolRegistry
from ..armory.armory import Armory
from ..armory.data_store import DataStore
from ..armory.stat_tools import StatsTools
from ..conversation.conversation import AgentConversation
from ..duck_orchestrator import DuckConversation
from ..utils.config_types import AgentConversationSettings, DuckContext, \
    SingleAgentSettings, Config, MultiAgentSettings
from ..utils.logger import duck_logger



def _build_agent(
        config: SingleAgentSettings,
        registry: ToolRegistry
) -> Agent:
    prompt = config.get('prompt')
    if not prompt:
        prompt_files = config.get("prompt_files")
        if not prompt_files:
            raise ValueError(f"You must provide either 'prompt' or 'prompt_files' for {config['name']}")

        prompt = f'\n'.join([Path(prompt_path).read_text(encoding="utf-8") for prompt_path in prompt_files])

    return Agent(
        name=config["name"],
        model=config["engine"],
        prompt=prompt,
        handoff_description=config.get("handoff_prompt", ""),
        tools=[],
        tool_registry=registry,
        handoffs=[]
    )


def _build_agents(
        settings: list[SingleAgentSettings],
) -> dict[str, tuple[Agent, SingleAgentSettings]]:
    agents = {}

    # Initial agent setup
    for agent_settings in settings:
        agent = _build_agent(agent_settings)
        agents[agent_settings['name']] = agent, agent_settings

    # Add on agent handoffs
    for agent_settings in settings:
        agent_name = agent_settings['name']
        agent = agents[agent_name][0]
        handoff_targets = agent_settings.get('handoffs', [])

        handoffs = [agents[target][0] for target in handoff_targets]
        agent.handoffs = handoffs

    return agents


def _get_starting_agent(settings: MultiAgentSettings):
    return settings.get('starting_agent', settings['agents'][0]['name'])


# noinspection PyTypeChecker
_tool_registry: ToolRegistry = None


def _add_tools_to_agents(agents: Iterable[tuple[Agent, SingleAgentSettings]], tool_registry: ToolRegistry):
    for agent, settings in agents:
        tools = [
            tool_registry.get_tool(tool)
            for tool in settings.get('tools', [])
            if tool in tool_registry.get_all_tool_names()
        ]
        agent.tools = tools

def _get_tool_registry(config: Config) -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()

        if 'dataset_folder_locations' in config:
            data_store = DataStore(config['dataset_folder_locations'])
            stat_tools = StatsTools(data_store)
            _tool_registry.scrub_tools(stat_tools)
        else:
            duck_logger.warning("**No dataset folder locations provided in config**")

    return _tool_registry


def build_agent_conversation_duck(
        name: str,
        config: Config,
        settings: AgentConversationSettings,
        bot,
        record_message: RecordMessage,
) -> DuckConversation:
    coordinator = AgentCoordinator()

    tool_registry = _get_tool_registry(config)

    conversation_agents = _build_agents(settings['agents'])
    _add_tools_to_agents(conversation_agents.values(), tool_registry)

    for agent in conversation_agents.values():
        coordinator.register_agent(agent[0])

    starting_agent = settings.get('starting_agent')

    agent_conversation = AgentConversation(
        name,
        settings['introduction'],
        genai_clients,
        starting_agent,
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
