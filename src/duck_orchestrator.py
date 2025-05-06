import random
from pathlib import Path
from typing import Protocol

from quest import step, alias

from conversation.conversation import GPTMessage
from metrics.feedback import GetConvoFeedback
from utils.config_types import ServerConfig
from utils.duck_breeds import DuckBreeds
from utils.protocols import Message
from workflows.basic_prompt_workflow import SetupConversation


class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...


class SetupConversation(Protocol):
    async def __call__(self, thread_id: int, prompt: str, initial_message: Message) -> list[GPTMessage]: ...


class DuckOrchestrator:
    def __init__(self,
                 server_config: dict[str, ServerConfig],
                 setup_thread: SetupThread,
                 setup_conversation: SetupConversation,
                 get_feedback: GetConvoFeedback
                 ):

        self._server_config = server_config
        self._setup_thread = step(setup_thread)
        self._setup_conversation = step(setup_conversation)
        self._get_feedback = step(get_feedback)

    def _get_config_info(self, channel_id: int, initial_message: Message):
        # Find the channel configuration using the channel_id
        channel_config = next(
            channel
            for server in self._server_config.values()
            for channel in server["channels"]
            if channel["channel_id"] == channel_id
        )

        # Check if feedback exists and store the result
        if channel_config.feedback_config is not None:
            feedback_config_exists = True
        else:
            feedback_config_exists = False

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

        # Get a random duck type based on the weights
        ducks = channel_config["duck"].list()
        items = []
        weights = []
        for duck in ducks:
            items.append(duck["workflow_type"])
            weights.append(duck["weight"])
        duck_type = random.choices(items, weights=weights, k=1)[0]

        return prompt, engine, timeout, duck_name, duck_type, feedback_config_exists

    async def __call__(self, channel_id: int, initial_message: Message, timeout=600):

        # set up the duck
        prompt, engine, timeout, duck_name, duck_type, feedback_config_exists = self._get_config_info(channel_id, initial_message)

        workflow = DuckBreeds[duck_type]

        # Set up a thread
        thread_id = await self._setup_thread(initial_message)

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        async with alias(str(thread_id)):
            # call duck workflow based on workflow
            await self._have_conversation(thread_id, engine, message_history, timeout)

        # determine if feedback is needed based on what the config says
        if feedback_config_exists:
            guild_id = initial_message['guild_id']
            user_id = initial_message['author_id']
            await self._get_feedback(duck_name, guild_id, thread_id, user_id, channel_id)
