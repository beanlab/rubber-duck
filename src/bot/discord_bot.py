import io

import discord
import requests

from ..utils.config_types import FileData
from ..utils.logger import duck_logger
from ..utils.protocols import Attachment, Message


def as_attachment(attachment):
    return Attachment(
        attachment_id=attachment.id,
        description=attachment.description,
        filename=attachment.filename,
        size=attachment.size,
        url=attachment.url
    )


# make this comprehension
def as_message(message: discord.Message) -> Message:
    return Message(
        guild_id=message.guild.id,
        channel_name=message.channel.name,
        channel_id=message.channel.id,
        author_id=message.author.id,
        author_name=message.author.name,
        author_mention=message.author.mention,
        message_id=message.id,
        content=message.content,
        files=[as_attachment(a) for a in message.attachments]
    )


def _parse_blocks(text: str, limit=1990):
    tick = '`'
    fence = tick * 3
    block = ""
    current_fence = ""
    for line in text.splitlines():
        if len(block) + len(line) > limit:
            if block:
                if current_fence:
                    block += fence
                    yield block
                    block = current_fence
                else:
                    yield block
                    block = ""
            else:
                # REALLY long line
                while len(line) > limit:
                    yield line[:limit]
                    line = line[limit:]

        if line.strip().startswith(fence):
            if current_fence:
                current_fence = ""
            else:
                if block:
                    yield block
                current_fence = line
                block = ""

        block += ('\n' + line) if block else line

    if block:
        yield block


class DiscordBot(discord.Client):
    def __init__(self):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings
        intents.message_content = True
        super().__init__(intents=intents)
        self._rubber_duck = None
        self._admin_channel = None  # Will be set when rubber duck app is set

    def set_duck_app(self, rubber_duck, admin_channel_id: int):
        self._rubber_duck = rubber_duck
        self._admin_channel = admin_channel_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def on_ready(self):
        # print out information when the bot wakes up
        duck_logger.info('Logged in as')
        duck_logger.info(self.user.name)
        duck_logger.info(self.user.id)
        duck_logger.info('Starting workflow manager')

        try:
            await self.send_message(self._admin_channel, 'Duck online')
        except:
            duck_logger.error(f'Unable to message channel {self._admin_channel}')

        duck_logger.info('------')

    async def close(self):
        duck_logger.warning("-- Suspending --")
        await super().close()

    async def on_message(self, message: discord.Message):
        if self._rubber_duck is None:
            return

        # ignore messages from the bot itself
        if message.author.id == self.user.id:
            return

        # ignore messages from other bots
        if message.author.bot:
            return

        # ignore messages that start with //
        if message.content.startswith('//'):
            return

        await self._rubber_duck.route_message(as_message(message))

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        # Ignore messages from the bot or other bots
        if user.id == self.user.id or user.bot:
            return

        await self._rubber_duck.route_reaction(reaction.emoji, reaction.message.id, user.id)

    #
    # Methods for message-handling protocols
    #

    def _make_discord_file(self, file: FileData | discord.File) -> discord.File:
        if isinstance(file, discord.File):
            return file
        if isinstance(file, tuple):
            return discord.File(io.BytesIO(file[1]), filename=file[0])
        if isinstance(file, dict):
            return discord.File(io.BytesIO(file['bytes']), filename=file['filename'])

        raise NotImplementedError(f"Unsupported file type: {file}")

    async def send_message(self, channel_id, message: str = None, file: FileData = None, view=None) -> int:
        channel = self.get_channel(channel_id)
        # try catch it and fetch the channel if it is not found
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except Exception:
                duck_logger.exception(f'Tried to send message on {channel_id}, but no channel found.')
                raise

        if message:
            for block in _parse_blocks(message):
                curr_message = await channel.send(block)
            # noinspection PyUnboundLocalVariable
            return curr_message.id

        if file is not None:
            files_to_send = []
            if not isinstance(file, list):
                files_to_send.append(file)
            else:
                files_to_send = file

            file_to_send = [self._make_discord_file(file) for file in files_to_send]
            curr_message = await channel.send(files=file_to_send)
            return curr_message.id

        if view is not None:
            return (await channel.send(view=view)).id

        raise Exception('Must send message, file, or view')

    async def edit_message(self, channel_id: int, message_id: int, new_content: str):
        channel = self.get_channel(channel_id)
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(content=new_content)
        except Exception as e:
            duck_logger.error(f"Could not edit message {message_id} in channel {channel_id}: {e}")

    async def add_reaction(self, channel_id: int, message_id: int, reaction: str):
        message = await (await self.fetch_channel(channel_id)).fetch_message(message_id)
        await message.add_reaction(reaction)

    class ChannelTyping:
        def __init__(self, fetch_channel, channel_id):
            self._fetch_channel = fetch_channel
            self._channel_id = channel_id

        async def __aenter__(self):
            channel = await self._fetch_channel(self._channel_id)
            self._typing = channel.typing()
            return await self._typing.__aenter__()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await self._typing.__aexit__(exc_type, exc_val, exc_tb)

    def typing(self, channel_id: int):
        return self.ChannelTyping(self.fetch_channel, channel_id)

    async def create_thread(self, parent_channel_id: int, title: str) -> int:
        # Create the private thread
        # Users/roles with "Manage Threads" will be able to see the private threads
        thread = await self.get_channel(parent_channel_id).create_thread(
            name=title,
            auto_archive_duration=60
        )
        return thread.id

    async def read_url(self, url: str) -> str:
        """
        Read a URL and return its content as a string.
        """
        try:
            return requests.get(url).text
        except Exception:
            duck_logger.exception(f"Error reading URL {url}")
            raise
