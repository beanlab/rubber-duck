import random
from typing import Protocol, Callable

from quest import step, alias


# How is this import supposed to be setup, becuase it surrently
from .utils.config_types import ChannelConfig
from .utils.protocols import Message


class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...


class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, settings: dict, initial_message: Message): ...


class DuckOrchestrator:
    def __init__(self,
                 setup_thread: SetupThread,
                 ducks: dict[str, HaveConversation],
                 remember_conversation: Callable[[int, int], None]
                 ):

        self._setup_thread = step(setup_thread)
        self._ducks = ducks
        self._remember_conversation = remember_conversation

    def _get_duck(self, channel_config: ChannelConfig) -> tuple[HaveConversation, dict]:
        possible_ducks = channel_config['ducks']

        if len(possible_ducks) == 1:
            duck_config = possible_ducks[0]
        else:
            weights = [dc.get('weight', 1) for dc in possible_ducks]
            duck_config = random.choices(possible_ducks, weights=weights, k=1)[0]

        duck = self._ducks[duck_config['workflow_type']]
        settings = duck_config['settings']
        return duck, settings

    async def __call__(self, channel_config: ChannelConfig, initial_message: Message):
        # Create a thread
        thread_id = await self._setup_thread(initial_message)

        # Run the duck
        duck, settings = self._get_duck(channel_config)

        async with alias(str(thread_id)):
            await duck(thread_id, settings, initial_message)

        # Remember conversation
        self._remember_conversation(channel_config['channel_id'], thread_id)
