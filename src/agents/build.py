from pathlib import Path
from typing import Any

from agents import Agent, AgentHooks, RunContextWrapper
from quest import step
from sqlalchemy.orm import Session

from .gen_ai import RecordUsage, AgentClient, MultiAgentClient
from ..armory.armory import Armory
from ..armory.data_store import DataStore
from ..armory.stat_tools import StatsTools
from ..duck_orchestrator import DuckConversationFactory
from ..storage.sql_quest import SqlBlobStorage
from ..utils.config_types import AgentConversationSettings, DuckContext, \
    SingleAgentSettings, MultiAgentSettings, Config


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


def build_agent(armory: Armory, config: SingleAgentSettings, agent_hooks: AgentHooks[DuckContext]) -> Agent[
    DuckContext]:
    tools = [
        armory.get_specific_tool(tool)
        for tool in config.get("tools", [])
        if tool in armory.get_all_tool_names()
    ]

    return Agent(
        name=config["name"],
        handoff_description=config.get("handoff_prompt", ""),
        instructions=Path(config["prompt_file"]).read_text(encoding="utf-8"),
        tools=tools,
        tool_use_behavior={"stop_at_tool_names": [tool.name for tool in tools if hasattr(tool, 'direct_send_message')]},
        model=config["engine"],
        hooks=agent_hooks,
        handoffs=[]
    )


def build_agents(
        armory: Armory,
        settings: MultiAgentSettings,
        agent_hooks: AgentHooks[DuckContext]
) -> dict[str, Agent[DuckContext]]:
    agents = {}

    # Initial agent setup
    for agent_settings in settings['individual_agent_settings']:
        agent = build_agent(armory, agent_settings, agent_hooks)
        agents[agent_settings['name']] = agent

    # Add on agent handoffs
    for agent_settings in settings['individual_agent_settings']:
        agent_name = agent_settings['name']
        agent = agents[agent_name]
        handoff_targets = agent_settings.get('handoffs', [])

        handoffs = [agents[target] for target in handoff_targets]
        agent.handoffs = handoffs

    return agents


def build_agent_conversation_duck(
        name: str,
        config: Config,
        metrics_handler,
        bot,
        settings: AgentConversationSettings,
        sql_session: Session,
        record_usage: RecordUsage
) -> DuckConversationFactory:
    armory = Armory()
    if 'dataset_folder_locations' in config:
        data_store = DataStore(config['dataset_folder_locations'])
        stat_tools = StatsTools(data_store)
        armory.scrub_tools(stat_tools)

    usage_hooks = UsageAgentHooks(record_usage)

    agent_type = settings['agent_type']

    match agent_type:
        case 'single-agent':
            agent = build_agent(armory, settings['agent_settings'], usage_hooks)
            return AgentClient(
                agent,
                settings.get('introduction', 'Hello. How can I help you?'),
                bot.typing
            )

        case 'multi-agent':
            last_agent_blob_storage = SqlBlobStorage('last_agent_state', sql_session)
            agents = build_agents(armory, settings['agent_settings'], usage_hooks)
            agent_client = MultiAgentClient(
                agents,
                settings['agent_settings']['starting_agent'],
                settings.get('introduction', 'Hello. How can I help you?'),
                bot.typing,
                last_agent_blob_storage,

            )

        case _:
            raise NotImplementedError(f'Agent type {agent_type} not implemented.')

    ai_completion_retry_protocol = config['ai_completion_retry_protocol']
    retryable_ai_client = RetryableGenAI(
        agent_client,
        bot.send_message,
        bot.typing,
        ai_completion_retry_protocol
    )

    agent_conversation = AgentConversation(
        name,
        retryable_ai_client,
        metrics_handler.record_message,
        bot.send_message,
        bot.add_reaction,
        settings['timeout'],
        armory
    )

    return agent_conversation
