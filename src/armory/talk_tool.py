import asyncio

from quest import queue

from .tools import register_tool
from ..utils.config_types import DuckContext
from ..utils.protocols import Message


class TalkTool:
    def __init__(self, send_message, typing, record_message, wait_for_user_timeout: int = 60):
        self._send_message = send_message
        self._typing = typing
        self._wait_for_user_timeout = wait_for_user_timeout
        self._record_message = record_message

    @register_tool
    async def talk_to_user(self, ctx: DuckContext, query: str) -> str:
        """
        The only way to talk to the user or to continue a conversation with them. This tool must be used
        to communicate. If you want to share information with the user, you must use this tool. When you have nothing left
        to tell the user, you do not have to call this tool.
        :param query: str: The message to send to the user.
        :return: responses: str: The response from the user.
        """
        await self._typing.stop(ctx.thread_id)
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
            await self._typing.start(ctx.thread_id)
            return message['content']
        except asyncio.TimeoutError:
            return "Conversation timed out. Please try again."

    @register_tool
    async def send_file(self, ctx: DuckContext, output: str):
        filename = "structured_output.txt"
        file_data = (filename, output.encode("utf-8"))
        await self._send_message(ctx.thread_id, message="Structured Output: ")
        await self._send_message(ctx.thread_id, file=file_data)
        await self._send_message(ctx.thread_id, message="Output: ")

