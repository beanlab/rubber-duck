import asyncio
import json

import yaml
from quest import queue, step

from .tools import register_tool
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger
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
    async def start_discord_conversation(self, ctx: DuckContext) -> str:
        """
        Start a conversation with the user to get the guild id of the new server. Always called at the beginning of a new conversation.
        :param ctx:
        :return:
        """
        await self.send_message_to_user(ctx, "What is the guild id of the new server?")
        guild = await self.receive_message_from_user(ctx)
        await self.send_message_to_user(ctx, "This bot requires you to accept the bot into the newly created server.\n Copy the link below into your newly created server\n Once you have done this, please type 'done' to continue.")
        await self.send_message_to_user(ctx, "```https://discord.com/oauth2/authorize?client_id=1329497251265122344&permissions=126000&scope=bot```")
        response = await self.receive_message_from_user(ctx)
        if "done" not in response.lower():
            await self.send_message_to_user(ctx, "You did not type 'done'. Exiting.")
            return "User did not type 'done'. User exited. Ending conversation."
        else:
            return f"The user's guild_id is: **{guild}**"

    @register_tool
    async def send_file(self, ctx: DuckContext, file_name: str, file_contents: str):
        """
        Send a file to the user as an attachment. Validates YAML/JSON if applicable.

        :param file_name: str: The name of the file to send.
        :param file_contents: str: The text content of the file to send.
        """
        try:
            if file_name.endswith(('.yaml', '.yml')):
                yaml.safe_load(file_contents)  # raises if invalid
            elif file_name.endswith('.json'):
                json.loads(file_contents)      # raises if invalid
        except Exception as e:
            duck_logger.debug(f"File validation failed for {file_name}: {e}")

        # Encode to bytes and send
        file_data = (file_name, file_contents.encode("utf-8"))
        await self._send_message(ctx.thread_id, file=file_data)

