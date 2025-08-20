import asyncio

from quest import queue, step

from .tools import register_tool
from ..utils.config_types import DuckContext
from ..utils.protocols import Message


class TalkTool:
    def __init__(self, send_message):
        self._send_message = step(send_message)

    @register_tool
    async def talk_to_user(self, ctx: DuckContext, message_to_user: str) -> str:
        """
        The only way to talk to the user or to continue a conversation with them. This tool must be used
        to communicate. If you want to share information with the user, you must use this tool. When you have nothing left
        to tell the user, you do not have to call this tool.
        :param message_to_user: str: The message to send to the user.
        :return: responses: str: The response from the user.
        """
        await self._send_message(ctx.thread_id, message_to_user)
        try:
            async with queue('messages', None) as messages:
                message: Message = await asyncio.wait_for(
                    messages.get(),
                    timeout=ctx.timeout
                )
            return message['content']
        except asyncio.TimeoutError:
            return "SYSTEM: The user has left. End the conversation."

    @register_tool
    async def send_file(self, ctx: DuckContext, file_name: str, file_text: str):
        """
        Send a file to the user. The file will be sent as an attachment in the conversation thread.
        :param file_name: str: The name of the file to send.
        :param file_text: str: The text content of the file to send.
        """
        file_data = (file_name, file_text.encode("utf-8"))
        await self._send_message(ctx.thread_id, file=file_data)
