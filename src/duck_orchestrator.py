import asyncio
import uuid
from collections.abc import Callable
from contextlib import AsyncExitStack

from quest import step, alias

from .duck_protocols import DuckContext, DuckConversation
from .metrics.feedback_manager import FeedbackData
from .utils.config_types import ChannelConfig, CHANNEL_ID
from .utils.logger import duck_logger, thread_id_context
from .utils.protocols import Message


_CONVERSATION_RESTARTED = "conversation restarted"


class DuckOrchestrator:
    def __init__(self,
                 setup_conversation,
                 send_message,
                 add_reaction,
                 ducks: dict[CHANNEL_ID, DuckConversation],
                 remember_conversation: Callable[[FeedbackData], None],
                 ):

        self._send_message = step(send_message)
        self._add_reaction = step(add_reaction)
        self._ducks = ducks
        self._remember_conversation = remember_conversation
        self._setup_conversation = setup_conversation
        self._locks = {}
        self._running = {}
        self._closing = set()

    async def stop_conversation(self, thread_id):
        task = self._running.get(thread_id)
        if task is not None:
            if thread_id not in self._closing:
                task.cancel(_CONVERSATION_RESTARTED)
            await task

    @step
    async def _setup_thread(self, message: Message) -> int:
        conversation = await self._setup_conversation(
            message['guild_id'], message['channel_id'],
            message['author_id'], message['author_mention'],
        )
        return conversation.thread_id

    def _get_duck(self, channel_id: int) -> DuckConversation:
        duck = self._ducks.get(channel_id)
        if not duck:
            raise ValueError(f'No duck configured for channel {channel_id}')
        return duck

    async def _run_duck(self, duck: DuckConversation, context: DuckContext, initial_message: Message):
        try:
            if 'duck' in initial_message['content']:
                await self._add_reaction(initial_message['channel_id'], initial_message['message_id'], "🦆")
            await self._send_message(context.thread_id, '*A new conversation has started.*')
            await duck(context)
        except asyncio.CancelledError as ex:
            if ex.args != (_CONVERSATION_RESTARTED,):
                raise
        except Exception:
            error_code = uuid.uuid4().hex[:8].upper()
            duck_logger.exception('Error: ' + error_code)
            await self._send_message(context.thread_id, f'😵 **Error code {error_code}** 😵\n')

    async def __call__(self, channel_config: ChannelConfig, initial_message: Message):
        duck = self._get_duck(channel_config['channel_id'])
        key = initial_message['guild_id'], initial_message['author_id'], channel_config['channel_id']

        async with AsyncExitStack() as thread_alias:
            # shortcut: one bot process; use a DB reservation before horizontal scaling.
            async with self._locks.setdefault(key, asyncio.Lock()):
                thread_id = await self._setup_thread(initial_message)
                await self.stop_conversation(thread_id)
                # Register the alias before another opener can replace this task.
                await thread_alias.enter_async_context(alias(str(thread_id)))
                self._running[thread_id] = asyncio.current_task()

            thread_id_context.set(thread_id)
            context = DuckContext(
                guild_id=initial_message['guild_id'],
                parent_channel_id=channel_config['channel_id'],
                author_id=initial_message['author_id'],
                author_mention=initial_message['author_mention'],
                content=initial_message['content'],
                conversation_id=initial_message['message_id'],
                thread_id=thread_id,
                timeout=channel_config.get('timeout', 60)
            )

            try:
                await self._run_duck(duck, context, initial_message)

                self._closing.add(thread_id)
                await thread_alias.aclose()
                await self._send_message(thread_id, '*This conversation has ended.*')

                self._remember_conversation(FeedbackData(
                    duck_type=duck.name,
                    guild_id=initial_message['guild_id'],
                    parent_channel_id=channel_config['channel_id'],
                    user_id=initial_message['author_id'],
                    conversation_thread_id=thread_id,
                    conversation_id=initial_message['message_id'],
                ))
            finally:
                self._running.pop(thread_id, None)
                self._closing.discard(thread_id)
