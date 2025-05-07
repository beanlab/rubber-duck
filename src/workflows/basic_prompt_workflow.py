from pathlib import Path
from typing import Protocol

from quest import step, alias

from ..conversation.conversation import GPTMessage
from ..metrics.feedback import GetConvoFeedback
from ..utils.config_types import ServerConfig
from ..utils.protocols import Message


class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...

    """Returns the thread ID"""


class SetupConversation(Protocol):
    async def __call__(self, thread_id: int, prompt: str, initial_message: Message) -> list[GPTMessage]: ...


class BasicPromptWorkflow:
    def __init__(self,
                 server_config: dict[str, ServerConfig],
                 default_config: dict,
                 setup_thread: SetupThread,
                 setup_conversation: SetupConversation,
                 have_conversation: HaveConversation,
                 get_feedback: GetConvoFeedback,
                 ):

        self._server_config = server_config
        self._default_bot_config = default_config

        # Make a rubber duck per channel
        self._setup_thread = step(setup_thread)
        self._setup_conversation = step(setup_conversation)
        self._have_conversation = step(have_conversation)
        self._get_feedback = step(get_feedback)

    def _get_channel_settings(self, channel_id: int, initial_message: Message):
        # Find the channel configuration using the channel_id
        channel_config = next(
            channel
            for server in self._server_config.values()
            for channel in server["channels"]
            if channel["channel_id"] == channel_id
        )
        duck_config = channel_config["ducks"][0]
        duck_settings = duck_config["settings"]

        prompt_file = duck_settings["prompt_file"]
        if prompt_file:
            prompt = Path(prompt_file).read_text(encoding="utf-8")
        else:
            prompt = initial_message['content']

        # Get engine and timeout from duck settings, falling back to defaults if not set
        engine = duck_settings["engine"] or self._default_bot_config["engine"]
        timeout = duck_settings["timeout"] or self._default_bot_config["timeout"]
        duck_name = duck_config["name"]

        return prompt, engine, timeout, duck_name

    async def __call__(self, channel_id: int, initial_message: Message, timeout=600):
        prompt, engine, timeout, duck_name = self._get_channel_settings(channel_id, initial_message)

        thread_id = await self._setup_thread(initial_message)

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        async with alias(str(thread_id)):
            await self._have_conversation(thread_id, engine, message_history, timeout)


