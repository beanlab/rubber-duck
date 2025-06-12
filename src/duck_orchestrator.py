import random
import traceback as tb
import uuid
from typing import Protocol, Callable

from quest import step, alias

from .metrics.feedback_manager import FeedbackData
from .utils.config_types import ChannelConfig, DuckContext, CHANNEL_ID, DUCK_WEIGHT
from .utils.logger import duck_logger
from .utils.protocols import Message


class SetupThread(Protocol):
    async def __call__(self, parent_channel_id: int, author_mention: str, title: str) -> int: ...


class DuckConversation(Protocol):
    name: str

    async def __call__(self, context: DuckContext): ...


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
                 ducks: dict[CHANNEL_ID, list[tuple[DUCK_WEIGHT, DuckConversation]]],
                 remember_conversation: Callable[[FeedbackData], None]
                 ):

        self._setup_thread: SetupThread = step(setup_thread)
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._ducks = ducks
        self._remember_conversation = remember_conversation

    def _get_duck(self, channel_id: int) -> DuckConversation:
        possible_ducks = self._ducks.get(channel_id)

        if not possible_ducks:
            raise ValueError(f'No duck configured for channel {channel_id}')

        if len(possible_ducks) == 1:
            return possible_ducks[0][1]

        weights = [w for w, dk in possible_ducks]
        return random.choices(possible_ducks, weights=weights, k=1)[0][1]


    async def __call__(self, channel_config: ChannelConfig, initial_message: Message):

        # Select the duck
        duck = self._get_duck(initial_message['channel_id'])

        # Create a thread
        thread_id = await self._setup_thread(
            initial_message['channel_id'],
            initial_message['author_mention'],
            initial_message['content']
        )

        context = DuckContext(
            guild_id=initial_message['guild_id'],
            channel_id=initial_message['channel_id'],
            author_id=initial_message['author_id'],
            author_mention=initial_message['author_mention'],
            content=initial_message['content'],
            message_id=initial_message['message_id'],
            thread_id=thread_id,
            send_message=self._send_message
        )

        async with alias(str(thread_id)):
            try:
                await duck(context)

            except Exception as ex:
                error_message, error_code = generate_error_message(thread_id, ex)
                await self._send_message(thread_id, f'😵 **Error code {error_code}** 😵\n')
                await self._report_error(error_message)

        await self._send_message(thread_id, '*This conversation has been closed.*')

        # Remember the conversation
        self._remember_conversation(FeedbackData(
            duck_type=duck.name,
            guild_id=initial_message['guild_id'],
            parent_channel_id=channel_config['channel_id'],
            user_id=initial_message['author_id'],
            conversation_thread_id=thread_id
        ))
