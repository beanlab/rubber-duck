import asyncio

from quest import queue

from .tools import register_tool
from ..utils.config_types import DuckContext
from ..utils.protocols import Message


class TalkTool:
    def __init__(self, send_message, wait_for_user_timeout: int = 60):
        self.send_message = send_message
        self._wait_for_user_timeout = wait_for_user_timeout

    @register_tool
    async def talk_to_user(self, ctx: DuckContext, query: str) -> str:
        await self.send_message(ctx.thread_id, query)
        async with queue('messages', None) as messages:
            try:
                message: Message = await asyncio.wait_for(
                    messages.get(),
                    self._wait_for_user_timeout
                )
                return message['content']

            except asyncio.TimeoutError:
                await self.send_message(ctx.thread_id, "Conversation timed out. Please try again.")
