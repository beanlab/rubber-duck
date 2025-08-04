import asyncio

from quest import queue

from .tools import register_tool
from ..utils.config_types import DuckContext
from ..utils.protocols import Message


class TalkTool:
    def __init__(self, send_message, record_message, wait_for_user_timeout: int = 60):
        self._send_message = send_message
        self._wait_for_user_timeout = wait_for_user_timeout
        self._record_message = record_message

    @register_tool
    async def talk_to_user(self, ctx: DuckContext, query: str) -> str:
        """
        The only way to talk to the user or to continue a conversation with them. This tool must be used
        to communicate. If you want to share information with the user, you must use this tool.
        :param query: str: The message to send to the user.
        :return: responses: str: The response from the user.
        """
        await self._send_message(ctx.thread_id, query)
        await self._record_message(
            ctx.guild_id, ctx.thread_id, ctx.author_id, "assistant", query
        )
        try:
            async with queue('messages', None) as messages:
                message: Message = await asyncio.wait_for(
                    messages.get(),
                    timeout=self._wait_for_user_timeout
                )
            await self._record_message(
                ctx.guild_id, ctx.thread_id, ctx.author_id, "user",
                message['content']
            )
            return message['content']
        except asyncio.TimeoutError:
            return "Conversation timed out. Please try again."
