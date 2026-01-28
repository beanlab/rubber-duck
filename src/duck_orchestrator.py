import random
import traceback as tb
import uuid
from typing import Protocol, Callable

from quest import step, alias

from .metrics.feedback_manager import FeedbackData
from .utils.config_types import ChannelConfig, DuckContext, CHANNEL_ID, DUCK_WEIGHT
from .utils.logger import duck_logger, thread_id_context
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
                 add_reaction,
                 ducks: dict[CHANNEL_ID, DuckConversation],
                 remember_conversation: Callable[[FeedbackData], None]
                 ):

        self._setup_thread: SetupThread = step(setup_thread)
        self._send_message = step(send_message)
        self._add_reaction = step(add_reaction)
        self._ducks = ducks
        self._remember_conversation = remember_conversation

    def _get_duck(self, channel_id: int) -> DuckConversation:
        duck = self._ducks.get(channel_id)
        if not duck:
            raise ValueError(f'No duck configured for channel {channel_id}')
        return duck

    async def __call__(self, channel_config: ChannelConfig, initial_message: Message):

        if 'duck' in initial_message['content']:
            await self._add_reaction(initial_message['channel_id'], initial_message['message_id'], "🦆")

        duck = self._get_duck(initial_message['channel_id'])

        thread_id = await self._setup_thread(
            initial_message['channel_id'],
            initial_message['author_mention'],
            initial_message['content']
        )

        thread_id_context.set(thread_id)

        context = DuckContext(
            guild_id=initial_message['guild_id'],
            parent_channel_id=initial_message['channel_id'],
            author_id=initial_message['author_id'],
            author_mention=initial_message['author_mention'],
            content=initial_message['content'],
            message_id=initial_message['message_id'],
            thread_id=thread_id,
            timeout=channel_config.get('timeout', 60)
        )

        async with alias(str(thread_id)):
            try:
                await duck(context)

            except Exception as ex:
                error_message, error_code = generate_error_message(thread_id, ex)
                await self._send_message(thread_id, f'😵 **Error code {error_code}** 😵\n')
                duck_logger.exception("Error in duck conversation")

        await self._send_message(thread_id, '*This conversation has been closed.*')

        # Remember the conversation
        self._remember_conversation(FeedbackData(
            duck_type=duck.name,
            guild_id=initial_message['guild_id'],
            parent_channel_id=channel_config['channel_id'],
            user_id=initial_message['author_id'],
            conversation_thread_id=thread_id
        ))
