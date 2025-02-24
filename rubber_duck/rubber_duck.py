from pathlib import Path
from typing import TypedDict, Protocol, List

from quest import step, alias

from feedback import GetConvoFeedback
from protocols import Message
from conversation import GPTMessage


class ChannelConfig(TypedDict):
    name: str | None
    id: int | None
    prompt: str | None
    prompt_file: str | None
    engine: str | None
    timeout: int | None


class DuckConfig(TypedDict):
    defaults: ChannelConfig
    channels: list[ChannelConfig]


class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...

    """Returns the thread ID"""


class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600, conversation_history: List[GPTMessage] = None): ...


class RubberDuck:
    def __init__(self,
                 duck_config: DuckConfig,
                 setup_thread: SetupThread,
                 have_conversation: HaveConversation,
                 get_feedback: GetConvoFeedback,
                 ):

        self._channel_configs = {config['name']: config for config in duck_config['channels']}
        self._default_config = duck_config['defaults']
        self._setup_thread = step(setup_thread)
        self._have_conversation = step(have_conversation)
        self._get_feedback = step(get_feedback)

    def _get_channel_settings(self, channel_name: str, initial_message: Message):
        channel_config = self._channel_configs[channel_name]

        prompt = channel_config.get('prompt', None)
        if prompt is None:
            prompt_file = channel_config.get('prompt_file', None)
            if prompt_file is None:
                prompt = initial_message['content']
            else:
                prompt = Path(prompt_file).read_text()

        engine = channel_config.get('engine', self._default_config['engine'])

        timeout = channel_config.get('timeout', self._default_config['timeout'])

        return prompt, engine, timeout

    async def __call__(self, channel_name: str, initial_message: Message, conversation_history=None, timeout=600):
        prompt, engine, timeout = self._get_channel_settings(channel_name, initial_message)

        thread_id = await self._setup_thread(initial_message)

        async with alias(str(thread_id)):
            await self._have_conversation(thread_id, engine, prompt, initial_message, timeout, conversation_history)

        guild_id = initial_message['guild_id']
        user_id = initial_message['author_id']
        await self._get_feedback("rubber-duck", guild_id, thread_id, user_id)
