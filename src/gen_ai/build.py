from pathlib import Path
from typing import Any, Iterable

from agents import Agent, AgentHooks, RunContextWrapper, ModelSettings
from openai.types import Reasoning
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
        config: SingleAgentSettings,
        agent_hooks: AgentHooks[DuckContext],
) -> Agent[DuckContext]:
    prompt = config.get('prompt')
    if not prompt:
        prompt_files = config.get("prompt_files")
        if not prompt_files:
            raise ValueError(f"You must provide either 'prompt' or 'prompt_files' for {config['name']}")

        prompt = f'\n'.join([Path(prompt_path).read_text(encoding="utf-8") for prompt_path in prompt_files])

    tool_required = config.get("tool_required", "")
    if tool_required:
        model_settings = ModelSettings(
            tool_choice=tool_required
        )
    else:
        model_settings = ModelSettings(
            tool_choice="auto"
        )

    reasoning = config.get("reasoning", None)
    if reasoning:
        model_settings.reasoning = {"effort": reasoning}

    return Agent[DuckContext](
        model_settings=model_settings,
        name=config["name"],
        handoff_description=config.get("handoff_prompt", ""),
        instructions=prompt,
        tools=[],
        tool_use_behavior={},
        model=config["engine"],
        hooks=agent_hooks,
        handoffs=[]
    )


def _build_agents(
        agent_hooks: AgentHooks[DuckContext],
        settings: list[SingleAgentSettings],
) -> dict[str, tuple[Agent[DuckContext], SingleAgentSettings]]:
    agents = {}

    # Initial agent setup
    for agent_settings in settings:
        agent = _build_agent(agent_settings, agent_hooks)
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
_armory: Armory = None


def _add_tools_to_agents(agents: Iterable[tuple[Agent, SingleAgentSettings]], armory: Armory):
    for agent, settings in agents:
        tools = [
            armory.get_specific_tool(tool)
            for tool in settings.get('tools', [])
            if tool in armory.get_all_tool_names()
        ]
        agent.tools = tools

def _get_armory(config: Config, usage_hooks: UsageAgentHooks, send_message) -> Armory:
    global _armory
    if _armory is None:
        _armory = Armory(send_message)

        if 'dataset_folder_locations' in config:
            data_store = DataStore(config['dataset_folder_locations'])
            stat_tools = StatsTools(data_store)
            _armory.scrub_tools(stat_tools)
        else:
            duck_logger.warning("**No dataset folder locations provided in config**")

    all_tool_agents = []
    for agent_settings in config.get('agents_as_tools', []):
        agents = _build_agents(usage_hooks, agent_settings['agents'])
        all_tool_agents.extend(agents.values())
        head_agent = agents[_get_starting_agent(agent_settings)][0]
        _armory.add_agent_as_tool(head_agent, agent_settings['tool_name'], agent_settings['description'])

    _add_tools_to_agents(all_tool_agents, _armory)

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
    armory = _get_armory(config, usage_hooks, bot.send_message)

    conversation_agents = _build_agents(usage_hooks, settings['agents'])
    _add_tools_to_agents(conversation_agents.values(), armory)

    ai_completion_retry_protocol = config['ai_completion_retry_protocol']

    genai_clients = {
        name: RetryableGenAI(
            AgentClient(agent, bot.typing),
            bot.send_message,
            ai_completion_retry_protocol
        )
        for name, (agent, _) in conversation_agents.items()
    }

    starting_agent = settings.get('starting_agent')
    if not starting_agent:
        starting_agent = next(iter(genai_clients.keys()))

    agent_conversation = AgentConversation(
        name,
        settings.get('introduction'),
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
