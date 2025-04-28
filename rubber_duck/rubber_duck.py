import random
from pathlib import Path
from typing import TypedDict, Protocol

from quest import step, alias

from conversation import GPTMessage
from feedback import GetConvoFeedback
from protocols import Message


class DuckChannelConfig(TypedDict):
    name: str
    prompt: str | None
    prompt_file: str | None
    engine: str | None
    timeout: int | None
    weight: int | None


class ChannelConfig(TypedDict):
    channel_name: str | None
    channel_id: int | None
    ducks: list[DuckChannelConfig]


class DuckConfig(TypedDict):
    defaults: DuckChannelConfig
    channels: list[ChannelConfig]

class DefaultConfig(TypedDict):
    engine: str | None
    timeout: int | None


class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...

    """Returns the thread ID"""


class SetupConversation(Protocol):
    async def __call__(self, thread_id: int, prompt: str, initial_message: Message) -> list[GPTMessage]: ...


class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, engine: str, message_history: list[GPTMessage], timeout: int = 600): ...


class RubberDuck:
    def __init__(self,
                 duck_config: DuckConfig,
                 default_config: DefaultConfig,
                 setup_thread: SetupThread,
                 setup_conversation: SetupConversation,
                 have_conversation: HaveConversation,
                 get_feedback: GetConvoFeedback,
                 ):

        # Use comprehension to extract channel configurations by channel_id
        self._channel_configs = {
            config['channel_id']: config
            for server_config in duck_config.values()
            if isinstance(server_config, dict) and 'channels' in server_config
            for config in server_config['channels']
            if 'channel_id' in config
        }

        # Get defaults from the config
        self._default_config = duck_config.get('default_duck_settings', default_config)

        # Make a rubber duck per channel
        self._setup_thread = step(setup_thread)
        self._setup_conversation = step(setup_conversation)
        self._have_conversation = step(have_conversation)
        self._get_feedback = step(get_feedback)

    def _get_channel_settings(self, channel_id: int, initial_message: Message):
        # Retrieve the channel configuration using the channel_id
        channel_config = self._channel_configs[channel_id]

        config_options = []
        config_weights = []
        for duck in channel_config['ducks']:
            config_options.append(duck)
            config_weights.append(duck.get('weight', 1))

        channel_config = random.choices(config_options, weights=config_weights)[0]

        prompt = channel_config.get('prompt', None)
        if prompt is None:
            prompt_file = channel_config.get('prompt_file', None)
            if prompt_file is None:
                prompt = initial_message['content']
            else:
                prompt = Path(prompt_file).read_text()

        # Access the engine from channel_config, defaulting to self._default_config['engine'] if it's not set
        engine = channel_config.get('engine', self._default_config['engine'])

        # Access the timeout from channel_config, defaulting to self._default_config['timeout'] if it's not set
        timeout = channel_config.get('timeout', self._default_config['timeout'])

        duck_name = channel_config.get('name')

        return prompt, engine, timeout, duck_name

    async def __call__(self, channel_id: int, initial_message: Message, timeout=600):
        prompt, engine, timeout, duck_name = self._get_channel_settings(channel_id, initial_message)

        thread_id = await self._setup_thread(initial_message)

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        async with alias(str(thread_id)):
            await self._have_conversation(thread_id, engine, message_history, timeout)

        guild_id = initial_message['guild_id']
        user_id = initial_message['author_id']
        await self._get_feedback(duck_name, guild_id, thread_id, user_id)
