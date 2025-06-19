from pathlib import Path
from typing import Any

from agents import Agent, AgentHooks, RunContextWrapper
from quest import step

from .gen_ai import RecordUsage, AgentClient, RetryableGenAI, RecordMessage
from ..armory.armory import Armory
from ..armory.data_store import DataStore
from ..armory.stat_tools import StatsTools
from ..conversation.conversation import AgentConversation
from ..duck_orchestrator import DuckConversation
from ..utils.config_types import AgentConversationSettings, DuckContext, \
    SingleAgentSettings, Config, MultiAgentSettings
from ..utils.logger import duck_logger


class UsageAgentHooks(AgentHooks[DuckContext]):
    def __init__(self, record_usage):
        self._record_usage = step(record_usage)

    async def on_end(
            self,
            context: RunContextWrapper[DuckContext],
            agent: Agent[DuckContext],
            output: Any,
    ) -> None:
        usage = context.usage
        context = context.context
        await self._record_usage(
            context.guild_id,
            context.parent_channel_id,
            context.thread_id,
            context.author_id,
            agent.model,
            usage.input_tokens,
            usage.output_tokens,
            usage.input_tokens_cached if hasattr(usage, 'input_tokens_cached') else 0,
            usage.reasoning_tokens if hasattr(usage, 'reasoning_tokens') else 0
        )


def _build_agent(
        armory: Armory,
        config: SingleAgentSettings,
        agent_hooks: AgentHooks[DuckContext],
) -> Agent[DuckContext]:
    tools = [
        armory.get_specific_tool(tool)
        for tool in config.get("tools", [])
        if tool in armory.get_all_tool_names()
    ]

    prompt = config.get('prompt')
    if not prompt:
        prompt_files = config.get("prompt_files")
        prompt = f'\n--------\n'.join([Path(prompt_path).read_text(encoding="utf-8") for prompt_path in prompt_files])
        if not prompt_files:
            raise ValueError(f"You must provide either 'prompt' or 'prompt_file' for {config['name']}")

    return Agent(
        name=config["name"],
        handoff_description=config.get("handoff_prompt", ""),
        instructions=prompt,
        tools=tools,
        tool_use_behavior={"stop_at_tool_names": [tool.name for tool in tools if hasattr(tool, 'direct_send_message')]},
        model=config["engine"],
        hooks=agent_hooks,
        handoffs=[]
    )


def _build_agents(
        armory: Armory,
        agent_hooks: AgentHooks[DuckContext],
        settings: list[SingleAgentSettings],
) -> dict[str, Agent[DuckContext]]:
    agents = {}

    # Initial agent setup
    for agent_settings in settings:
        agent = _build_agent(armory, agent_settings, agent_hooks)
        agents[agent_settings['name']] = agent

    # Add on agent handoffs
    for agent_settings in settings:
        agent_name = agent_settings['name']
        agent = agents[agent_name]
        handoff_targets = agent_settings.get('handoffs', [])

        handoffs = [agents[target] for target in handoff_targets]
        agent.handoffs = handoffs

    return agents


def _get_starting_agent(settings: MultiAgentSettings):
    return settings.get('starting_agent', settings['agents'][0]['name'])


# noinspection PyTypeChecker
_armory: Armory = None


def _get_armory(config: Config, usage_hooks: UsageAgentHooks) -> Armory:
    global _armory
    if _armory is None:
        _armory = Armory()

        if 'dataset_folder_locations' in config:
            data_store = DataStore(config['dataset_folder_locations'])
            stat_tools = StatsTools(data_store)
            _armory.scrub_tools(stat_tools)
        else:
            duck_logger.warning("**No dataset folder locations provided in config**")

        # Agents used as tools don't get any tools of their own. We use an empty amory to make them.
        armory_for_agents_as_tools = Armory()

        for agent_settings in config.get('agents_as_tools', []):
            agents = _build_agents(armory_for_agents_as_tools, usage_hooks, agent_settings['agents'])
            head_agent = agents[_get_starting_agent(agent_settings)]
            _armory.add_agent_as_tool(head_agent, agent_settings['tool_name'], agent_settings['description'])

    return _armory


def build_agent_conversation_duck(
        name: str,
        config: Config,
        settings: AgentConversationSettings,
        bot,
        record_message: RecordMessage,
        record_usage: RecordUsage
) -> DuckConversation:
    usage_hooks = UsageAgentHooks(record_usage)
    armory = _get_armory(config, usage_hooks)

    agents = _build_agents(armory, usage_hooks, settings['agents'])

    ai_completion_retry_protocol = config['ai_completion_retry_protocol']

    genai_clients = {
        name: RetryableGenAI(
            AgentClient(agent, bot.typing),
            bot.send_message,
            ai_completion_retry_protocol
        )
        for name, agent in agents.items()
    }

    starting_agent = settings.get('starting_agent')
    if not starting_agent:
        starting_agent = next(iter(genai_clients.keys()))

    agent_conversation = AgentConversation(
        name,
        settings['introduction'],
        genai_clients,
        starting_agent,
        record_message,
        bot.send_message,
        bot.add_reaction,
        bot.read_url,
        bot.read_file,
        settings.get('timeout', 60*5),
        armory,
        settings.get('file_size_limit', 0),
        settings.get('file_type_ext', []),
    )

    return agent_conversation
