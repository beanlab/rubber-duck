import asyncio
import json

import yaml
from quest import queue, step

from .tools import register_tool
from ..utils.config_types import DuckContext
from ..utils.protocols import Message


class TalkTool:
    def __init__(self, send_message):
        self._send_message = step(send_message)

    @register_tool
    async def send_message_to_user(self, ctx: DuckContext, message_to_user: str):
        """
        Send a message to the user. This tool is used to send messages to the user in the conversation thread.
        :param ctx:
        :param message_to_user:
        :return:
        """
        await self._send_message(ctx.thread_id, message_to_user)

    @register_tool
    async def receive_message_from_user(self, ctx: DuckContext) -> str:
        """
        Wait for a message from the user. This tool is used to receive messages from the user.
        :return: responses: str: The response from the user.
        """
        try:
            async with queue('messages', None) as messages:
                message: Message = await asyncio.wait_for(
                    messages.get(),
                    timeout=ctx.timeout
                )
            return message['content']
        except asyncio.TimeoutError:
            return "SYSTEM: The user has not responded."

    @register_tool
    async def talk_to_user(self, ctx: DuckContext, message_to_user: str) -> str:
        """
        The only way to talk to the user or to continue a conversation with them. This tool must be used
        to communicate. If you want to share information with the user, you must use this tool. When you have nothing left
        to tell the user, you do not have to call this tool.
        :param message_to_user: str: The message to send to the user.
        :return: responses: str: The response from the user.
        """
        await self.send_message_to_user(ctx, message_to_user)
        return await self.receive_message_from_user(ctx)

    @register_tool
    async def send_text_file(self, ctx: DuckContext, file_name: str, file_text: str):
        """
        Send a file to the user. The file will be sent as an attachment in the conversation thread.
        :param file_name: str: The name of the file to send.
        :param file_text: str: The text content of the file to send.
        """
        file_data = (file_name, file_text.encode("utf-8"))
        await self._send_message(ctx.thread_id, file=file_data)

    @register_tool
    async def send_json_file(self, ctx: DuckContext, file_name: str, file_json: str):
        """
        Send a JSON file to the user. The file will be sent as an attachment in the conversation thread.
        :param file_name: str: The name of the file to send.
        :param file_json: str: The JSON content of the file to send (already a JSON-formatted string).
        """
        file_data = (file_name, file_json.encode("utf-8"))
        await self._send_message(ctx.thread_id, file=file_data)

    @register_tool
    async def send_yaml_file(self, ctx: DuckContext, file_name: str, file_json: str):
        """
        Convert a JSON string to YAML and send it as a file to the user.
        :param file_name: str: The name of the YAML file to send (should end with .yaml or .yml).
        :param file_json: str: The JSON content (string) to convert and send.
        """
        try:
            # Parse JSON string into Python dict
            data = json.loads(file_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON provided: {e}")

        # Convert to YAML (safe, readable formatting)
        yaml_str = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

        # Encode and send as file
        file_data = (file_name, yaml_str.encode("utf-8"))
        await self._send_message(ctx.thread_id, file=file_data)