import random
from pathlib import Path
from typing import Protocol

from quest import step, alias

from conversation.conversation import GPTMessage, HaveConversation
from metrics.feedback import GetConvoFeedback
from utils.config_types import ServerConfig
from utils.protocols import Message
from workflows.agentic_workflow import AgenticWorkflow
from workflows.basic_prompt_workflow import BasicPromptWorkflow
from workflows.socratic_workflow import SocraticWorkflow


class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...


class SetupConversation(Protocol):
    async def __call__(self, thread_id: int, prompt: str, initial_message: Message) -> list[GPTMessage]: ...


class DuckOrchestrator:
    def __init__(self,
                 server_config: dict[str, ServerConfig],
                 setup_thread: SetupThread,
                 setup_conversation: SetupConversation,
                 get_feedback: GetConvoFeedback,
                 conversation_types
                 ):

        self._server_config = server_config
        self._setup_thread = step(setup_thread)
        self._setup_conversation = step(setup_conversation)
        self._get_feedback = step(get_feedback)
        self._conversation_types = conversation_types
        self.duck_breeds = {
            "duck": BasicPromptWorkflow,
            "socratic": SocraticWorkflow,
            "agentic": AgenticWorkflow,
        }

    def _get_config_info(self, channel_id: int, initial_message: Message):
        # Find the channel configuration using the channel_id
        channel_config = next(
            channel
            for server in self._server_config.values()
            for channel in server["channels"]
            if channel["channel_id"] == channel_id
        )

        # Check if feedback_config exists (not just the key, but non-None)
        feedback_config_exists = "feedback_config" in channel_config

        # Get the ducks list
        ducks = channel_config["ducks"]
        if not ducks:
            raise ValueError(f"No ducks configured for channel {channel_id}")

        # Pick a random duck type based on weights
        items = [duck["workflow_type"] for duck in ducks]
        weights = [duck["weight"] for duck in ducks]
        duck_type = random.choices(items, weights=weights, k=1)[0]

        # Get the first duck's config and settings
        duck_config = ducks[0]
        duck_settings = duck_config["settings"]

        # Load prompt text from file if provided, else use initial message content
        prompt_file = duck_settings.get("prompt_file")
        if prompt_file:
            prompt_path = Path(prompt_file)
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file '{prompt_file}' not found")
            prompt = prompt_path.read_text(encoding="utf-8")
        else:
            prompt = initial_message['content']

        # Get engine and timeout, with fallback defaults
        engine = duck_settings.get("engine", "gpt-4")
        timeout = duck_settings.get("timeout", 600)
        duck_name = duck_config["name"]

        return prompt, engine, timeout, duck_name, duck_type, feedback_config_exists

    def _handle_duck_type(self, duck_type: str, settings:{})-> BasicPromptWorkflow | SocraticWorkflow | AgenticWorkflow:
        if duck_type == "duck":
            return BasicPromptWorkflow(self._conversation_types["standard_conversation"], settings["thread_id"], settings["engine"], settings["message_history"] ,settings["timeout"])
        elif duck_type == "socratic":
            return SocraticWorkflow(self._conversation_types["standard_conversation"], settings["thread_id"], settings["engine"], settings["message_history"] ,settings["timeout"])
        elif duck_type == "agentic":
            return AgenticWorkflow()
        else:
            raise ValueError(f"Unknown duck type: {duck_type}")

    async def __call__(self, channel_id: int, initial_message: Message, timeout=600):

        # set up the duck
        prompt, engine, timeout, duck_name, duck_type, feedback_config_exists = self._get_config_info(channel_id, initial_message)

        # Set up a thread
        thread_id = await self._setup_thread(initial_message)

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        settings = {
            "thread_id": thread_id,
            "engine": engine,
            "message_history": message_history,
            "timeout": timeout
        }

        # call duck workflow based on workflow
        async with alias(str(thread_id)):
            workflow = self._handle_duck_type(duck_type,settings)
            await workflow()

        # determine if feedback is needed based on what the config says
        if feedback_config_exists:
            guild_id = initial_message['guild_id']
            user_id = initial_message['author_id']
            await self._get_feedback(duck_name, guild_id, thread_id, user_id, channel_id)
