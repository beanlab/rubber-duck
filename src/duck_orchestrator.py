import random
import re
import traceback as tb
import uuid
from typing import Protocol, Callable

from quest import step, alias

from .metrics.feedback_manager import FeedbackData
from .utils.config_types import ChannelConfig, DuckConfig
from .utils.logger import duck_logger
from .utils.protocols import Message


class SetupThread(Protocol):
    async def __call__(self, initial_message: Message) -> int: ...


class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, settings: dict, initial_message: Message): ...


def generate_error_message(thread_id, ex):
    error_code = str(uuid.uuid4()).split('-')[0].upper()
    duck_logger.exception('Error: ' + error_code)
    error_message = (
        f'😵 **Error code {error_code}** 😵'
        f'\n<@#{thread_id}>'
        f'\n{ex}\n'
        '\n'.join(tb.format_exception(ex))
    )
    return error_message, error_code


class DuckOrchestrator:
    def __init__(self,
                 setup_thread: SetupThread,
                 send_message,
                 report_error,
                 ducks: dict[str, HaveConversation],
                 remember_conversation: Callable[[FeedbackData], None]
                 ):

        self._setup_thread = step(setup_thread)
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._ducks = ducks
        self._remember_conversation = remember_conversation

    def _get_duck_config(self, possible_ducks, initial_message: Message) -> DuckConfig | None:
        """
        Duck selection rules:
        - Go through ducks -> find the first one with a matching regex. Return it.
        - If no regex matched, look at all ducks without a regex configured, and choose among weights.
        """

        for duck_config in possible_ducks:
            if (regex := duck_config.get('regex')) and re.match(regex, initial_message['content']):
                return duck_config

        possible_ducks = [duck_config for duck_config in possible_ducks if 'regex' not in duck_config]

        if not possible_ducks:
            return None

        if len(possible_ducks) == 1:
            return possible_ducks[0]

        weights = [dc.get('weight', 1) for dc in possible_ducks]
        return random.choices(possible_ducks, weights=weights, k=1)[0]

    async def __call__(self, channel_config: ChannelConfig, initial_message: Message):
        # Select the duck
        duck_config = self._get_duck_config(channel_config['ducks'], initial_message)
        if duck_config is None:
            return

        duck_type = duck_config['workflow_type']
        duck = self._ducks[duck_type]
        settings = duck_config['settings']

        # Create a thread
        thread_id = await self._setup_thread(initial_message)

        async with alias(str(thread_id)):
            try:
                await duck(thread_id, settings, initial_message)

            except Exception as ex:
                error_message, error_code = generate_error_message(thread_id, ex)
                await self._send_message(thread_id, f'😵 **Error code {error_code}** 😵\n')
                await self._report_error(error_message, True)

        await self._send_message(thread_id, '*This conversation has been closed.*')

        # Remember conversation
        self._remember_conversation(FeedbackData(
            duck_type=duck_type,
            guild_id=initial_message['guild_id'],
            parent_channel_id=channel_config['channel_id'],
            user_id=initial_message['author_id'],
            conversation_thread_id=thread_id
        ))