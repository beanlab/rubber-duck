import random
from pathlib import Path
from typing import Protocol

from quest import step

from conversation.conversation import GPTMessage
from metrics.feedback import GetConvoFeedback
from utils.config_types import ServerConfig
from utils.protocols import Message
from workflows.basic_prompt_workflow import SetupConversation


class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...

class SetupConversation(Protocol):
    async def __call__(self, thread_id: int, prompt: str, initial_message: Message) -> list[GPTMessage]: ...


class DuckOrchestrator:
    # dictionary

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

    def _get_random_duck(self, channel_id: int) -> str:
        channel_config = next(
            channel
            for server in self._server_config.values()
            for channel in server["channels"]
            if channel["channel_id"] == channel_id
        )
        ducks = channel_config["ducks"].list()
        items = []
        weights = []
        for duck in ducks:
            items.append(duck["workflow_type"])
            weights.append(duck["weight"])

        return random.choices(items, weights=weights, k=1)[0]


    # call
    async def __call__(self, channel_id: int,initial_message: Message, timeout=600):

        # find in dict and determine which duck to use
        duck_key = self._get_random_duck(channel_id) # returns "socratic, duck, canvas register"

        # set up the duck
        prompt, engine, timeout, duck_name = self._get_config_info(channel_id, initial_message)

        # Set up a thread
        thread_id = await self._setup_thread(initial_message)

        # start workflow
        self._workflow_manager.start_workflow(duck_key, workflow_id, message)

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        async with alias(str(thread_id)):
            await self._have_conversation(thread_id, engine, message_history, timeout)

        # determine if feedback is needed based on what the config says


        guild_id = initial_message['guild_id']
        user_id = initial_message['author_id']
        await self._get_feedback(duck_name, guild_id, thread_id, user_id, channel_id)

