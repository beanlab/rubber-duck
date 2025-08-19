import asyncio

from quest import queue, step

from .tools import register_tool
from ..utils.config_types import DuckContext
from ..utils.protocols import Message


class TalkTool:
    def __init__(self, send_message, wait_for_user_timeout: int = 300):
        self._send_message = step(send_message)
        self._wait_for_user_timeout = wait_for_user_timeout

    @register_tool
    async def talk_to_user(self, ctx: DuckContext, query: str) -> str:
        """
        The only way to talk to the user or to continue a conversation with them. This tool must be used
        to communicate. If you want to share information with the user, you must use this tool. When you have nothing left
        to tell the user, you do not have to call this tool.
        :param query: str: The message to send to the user.
        :return: responses: str: The response from the user.
        """
        await self._send_message(ctx.thread_id, query)
        try:
            async with queue('messages', None) as messages:
                message: Message = await asyncio.wait_for(
                    messages.get(),
                    timeout=self._wait_for_user_timeout
                )
            return message['content']
        except asyncio.TimeoutError:
            return "SYSTEM: The user has left. End the conversation."

    @register_tool
    async def send_file(self, ctx: DuckContext, output: str):
        """
        Send a file to the user. The output is a string that will be structured as a dictionary
        :param ctx:
        :param output:
        :return:
        """
        filename = "structured_output.txt"
        file_data = (filename, output.encode("utf-8"))
        await self._send_message(ctx.thread_id, message="Structured Output: ")
        await self._send_message(ctx.thread_id, file=file_data)
        await self._send_message(ctx.thread_id, message="Output: ")
