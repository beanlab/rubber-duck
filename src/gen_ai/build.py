from pathlib import Path

from .gen_ai import RecordMessage, Agent, AIClient
from ..armory.armory import Armory
from ..armory.data_store import DataStore
from ..armory.stat_tools import StatsTools
from ..armory.talk_tool import TalkTool
from ..conversation.conversation import AgentConversation
from ..duck_orchestrator import DuckConversation
from ..outputs.structured_outputs import schema_to_model
from ..utils.config_types import AgentConversationSettings, SingleAgentSettings, Config, AgentAsToolSettings
from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage


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

    output_fields = config.get("output_format", None)
    output_model = None
    if output_fields:
        output_model = schema_to_model(config["name"] + "Output", output_fields)

    agent = Agent(
        name=config["name"],
        prompt=prompt,
        model=config["engine"],
        tools=config["tools"],
        usage=config["usage"],
        tool_settings=tool_required,
        output_format=output_model,
        reasoning=config.get("reasoning", None)
    )
    return agent


def _register_agent_tools(
        agent_tool_settings: list[AgentAsToolSettings],
        armory: Armory,
        client: AIClient
) -> None:
    """Add agent tools to the armory."""
    for settings in agent_tool_settings:
        tool_name = settings['tool_name']
        tool_description = settings['description']
        agent = _build_agent(settings['agent'])
        armory.add_tool(client.build_agent_tool(agent, tool_name, tool_description))


def _add_agent_tools(config: Config, client: AIClient) -> None:
    _register_agent_tools(config['agents_as_tools'], _armory, client)


def _build_main_agent(
        agent_settings: SingleAgentSettings,
        agent_tool_settings: list[AgentAsToolSettings] | None,
        armory: Armory,
        client: AIClient
) -> Agent:
    main_agent = _build_agent(agent_settings)

    if agent_tool_settings:
        _register_agent_tools(agent_tool_settings, armory, client)

    return main_agent


# noinspection PyTypeChecker
_armory: Armory = None
# noinspection PyTypeChecker
_ai_client: AIClient = None


def _get_ai_client(armory) -> AIClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient(armory)

    return _ai_client


def _get_armory(config: Config, send_message, typing, record_message) -> Armory:
    global _armory
    if _armory is None:
        _armory = Armory(send_message)

        if 'dataset_folder_locations' in config:
            data_store = DataStore(config['dataset_folder_locations'])
            stat_tools = StatsTools(data_store)
            _armory.scrub_tools(stat_tools)
        else:
            duck_logger.warning("**No dataset folder locations provided in config**")

        talk_tool = TalkTool(send_message, typing, record_message, 30)
        _armory.scrub_tools(talk_tool)

    return _armory


def build_agent_conversation_duck(
        name: str,
        config: Config,
        settings: AgentConversationSettings,
        record_message: RecordMessage,
        send_message: SendMessage,
        typing
) -> DuckConversation:
    # Same for each duck
    armory = _get_armory(config, send_message, typing, record_message)
    ai_client = _get_ai_client(armory)

    # Different for each duck
    _add_agent_tools(config, ai_client)
    starting_agent = _build_main_agent(settings['agent'], settings.get('agents_as_tools', None), armory, ai_client)

    agent_conversation = AgentConversation(
        name,
        starting_agent,
        ai_client,
        typing,
    )

    return agent_conversation
