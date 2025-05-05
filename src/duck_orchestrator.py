import random
from pathlib import Path
from typing import Protocol

from quest import step

from utils.config_types import ServerConfig
from utils.protocols import Message

class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...

class DuckOrchestrator:
    # dictionary

    def __init__(self, server_config: dict[str, ServerConfig], setup_thread: SetupThread, workflow_manager):
        self._server_config = server_config
        self._setup_thread = step(setup_thread)

    def _get_config_info(self, channel_id: int, initial_message: Message):
        self._server_config['channel_id'] = channel_id

    def _get_random_duck(self, items, weights):
        items = self._server_config['channel_id']
        return random.choices(items, weights=weights, k=1)[0]


    # call
    async def __call__(self, initial_message: Message, timeout=600):

        # create thread
        thread_id = await self._setup_thread(initial_message)

        # determine which duck to use
        prompt, engine, timeout, duck_name = self._get_config_info(channel_id, initial_message)

        # find in dict
        # start workflow

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        async with alias(str(thread_id)):
            await self._have_conversation(thread_id, engine, message_history, timeout)

        # determine if feedback is needed based on what the config says


        guild_id = initial_message['guild_id']
        user_id = initial_message['author_id']
        await self._get_feedback(duck_name, guild_id, thread_id, user_id, channel_id)

