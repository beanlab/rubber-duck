from pathlib import Path
from typing import Optional, List

from discord.context_managers import Typing

from .gen_ai import RecordMessage, Agent, AIClient, RecordUsage
from ..armory.armory import Armory
from ..armory.data_store import DataStore
from ..armory.stat_tools import StatsTools
from ..armory.talk_tool import TalkTool
from ..conversation.conversation import AgentConversation
from ..utils.config_types import (
    AgentConversationSettings,
    SingleAgentSettings,
    Config,
    AgentAsToolSettings,
)
from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage


def _build_agent(config: SingleAgentSettings) -> Agent:
    prompt = config.get("prompt")
    if not prompt:
        prompt_files = config.get("prompt_files")
        if not prompt_files:
            raise ValueError(
                f"You must provide either 'prompt' or 'prompt_files' for {config['name']}"
            )
        prompt = "\n".join(
            [Path(prompt_path).read_text(encoding="utf-8") for prompt_path in prompt_files]
        )

    tool_required = config.get("tool_required", "auto")
    if tool_required not in ["auto", "required", "none"]:
        tool_required = {"type": "function", "name": tool_required}

    output_schema = config.get("output_format", None)

    return Agent(
        name=config["name"],
        prompt=prompt,
        model=config["engine"],
        tools=config["tools"],
        tool_settings=tool_required,
        output_format=output_schema,
        reasoning=config.get("reasoning"),
    )


class SystemBuilder:
    def __init__(
            self,
            config: Config,
            send_message: SendMessage,
            typing: Typing,
            record_message: RecordMessage,
            record_usage: RecordUsage,
    ):
        self.config = config
        self.send_message = send_message
        self.typing = typing
        self.record_message = record_message
        self.record_usage = record_usage

        self._armory: Optional[Armory] = None
        self._ai_client: Optional[AIClient] = None

    def armory(self) -> Armory:
        if self._armory is None:
            self._armory = Armory(self.send_message)

            dataset_dirs = self.config.get("dataset_folder_locations")
            if dataset_dirs:
                data_store = DataStore(dataset_dirs)
                stat_tools = StatsTools(data_store)
                self._armory.scrub_tools(stat_tools)
            else:
                duck_logger.warning("**No dataset folder locations provided in config**")

            talk_tool = TalkTool(self.send_message)
            self._armory.scrub_tools(talk_tool)

        return self._armory

    def ai_client(self) -> AIClient:
        if self._ai_client is None:
            self._ai_client = AIClient(
                self.armory(), self.typing, self.record_message, self.record_usage
            )
            self._agent_tools_add()
        return self._ai_client

    def _agent_tools_add(self) -> None:
        agents_as_tools: List[AgentAsToolSettings] = self.config.get("agents_as_tools", [])
        for settings in agents_as_tools:
            agent = _build_agent(settings["agent"])
            tool = self._ai_client.build_agent_tool(
                agent, settings["tool_name"], settings["doc_string"]
            )
            self.armory().add_tool(tool)

        self._agent_tools_added = True


_system: Optional[SystemBuilder] = None


def get_system(
        config: Config,
        send_message: SendMessage,
        typing: Typing,
        record_message: RecordMessage,
        record_usage: RecordUsage,
) -> SystemBuilder:
    global _system
    if _system is None:
        _system = SystemBuilder(config, send_message, typing, record_message, record_usage)
    return _system


def build_agent_conversation_duck(
        name: str,
        config: Config,
        settings: AgentConversationSettings,
        record_message: RecordMessage,
        send_message: SendMessage,
        record_usage: RecordUsage,
        typing,
) -> AgentConversation:

    system = get_system(config, send_message, typing, record_message, record_usage)

    ai_client = system.ai_client()
    starting_agent = _build_agent(settings["agent"])

    return AgentConversation(name, starting_agent, ai_client)
