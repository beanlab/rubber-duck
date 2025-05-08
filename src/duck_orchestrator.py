import random
from typing import Protocol, Callable

from quest import step, alias

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
                 remember_conversation: Callable[[ChannelConfig, int], None]
                 ):

        self._setup_thread = step(setup_thread)
        self._ducks = ducks
        self._remember_conversation = remember_conversation

    # def _get_config_info(self, channel_id: int, initial_message: Message):
    #     # Find the channel configuration using the channel_id
    #     channel_config = next(
    #         channel
    #         for server in self._channel_configs.values()
    #         for channel in server["channels"]
    #         if channel["channel_id"] == channel_id
    #     )
    #
    #     # Check if feedback exists and store the result
    #     if channel_config.feedback_config is not None:
    #         feedback_config_exists = True
    #     else:
    #         feedback_config_exists = False
    #
    #     duck_config = channel_config["ducks"][0]
    #     duck_settings = duck_config["settings"]
    #
    #     prompt_file = duck_settings["prompt_file"]
    #     if prompt_file:
    #         prompt = Path(prompt_file).read_text(encoding="utf-8")
    #     else:
    #         prompt = initial_message['content']
    #
    #     # Get engine and timeout from duck settings, falling back to defaults if not set
    #     engine = duck_settings["engine"] or self._default_bot_config["engine"]
    #     timeout = duck_settings["timeout"] or self._default_bot_config["timeout"]
    #     duck_name = duck_config["name"]
    #
    #     # Get a random duck type based on the weights
    #     ducks = channel_config["duck"].list()
    #     items = []
    #     weights = []
    #     for duck in ducks:
    #         items.append(duck["workflow_type"])
    #         weights.append(duck["weight"])
    #     duck_type = random.choices(items, weights=weights, k=1)[0]
    #
    #     return prompt, engine, timeout, duck_name, duck_type, feedback_config_exists

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
        self._remember_conversation(channel_config, thread_id)
