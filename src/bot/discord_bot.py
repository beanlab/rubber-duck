import logging

import discord

from ..commands.command import UsageMetricsCommand, MessagesMetricsCommand, FeedbackMetricsCommand, MetricsCommand, \
    StatusCommand, \
    ReportCommand, BashExecuteCommand, LogCommand, Command, ActiveWorkflowsCommand
from ..utils.protocols import Attachment, Message


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
        file=[as_attachment(attachment) for attachment in message.attachments]
    )


def as_attachment(attachment):
    return Attachment(
        attachment_id=attachment.id,
        description=attachment.description,
        filename=attachment.filename
    )


def create_commands(send_message, metrics_handler, reporter, active_workflow_function) -> list[Command]:
    # Create and return the list of commands
    return [
        messages := MessagesMetricsCommand(send_message, metrics_handler),
        usage := UsageMetricsCommand(send_message, metrics_handler),
        feedback := FeedbackMetricsCommand(send_message, metrics_handler),
        MetricsCommand(messages, usage, feedback),
        StatusCommand(send_message),
        ReportCommand(send_message, reporter),
        LogCommand(send_message, BashExecuteCommand(send_message)),
        ActiveWorkflowsCommand(send_message, active_workflow_function)
    ]


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
        self._command_channel = None  # Will be set when rubber duck app is set

    def set_duck_app(self, rubber_duck):
        self._rubber_duck = rubber_duck
        self._command_channel = rubber_duck._command_channel

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def on_ready(self):
        # print out information when the bot wakes up
        logging.info('Logged in as')
        logging.info(self.user.name)
        logging.info(self.user.id)
        logging.info('Starting workflow manager')

        try:
            await self.send_message(self._command_channel, 'Duck online')
        except:
            logging.exception(f'Unable to message channel {self._command_channel}')

        logging.info('------')

    async def close(self):
        logging.warning("-- Suspending --")
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

    async def send_message(self, channel_id, message: str, file=None, view=None) -> int:
        channel = await self.fetch_channel(channel_id)
        if channel is None:
            # await self.report_error(f'Tried to send message on {channel_id}, but no channel found.')
            logging.error(f'Tried to send message on {channel_id}, but no channel found.')
            raise Exception(f'No channel id {channel_id}')

        curr_message = None

        for block in _parse_blocks(message):
            curr_message = await channel.send(block)

        if file is not None:
            if isinstance(file, list):
                curr_message = await channel.send("", files=file)
                # TODO: check that all instances are discord.File objects.
            elif not isinstance(file, discord.File):
                file = discord.File(file)
                curr_message = await channel.send("", file=file)
            else:
                curr_message = await channel.send("", file=file)

        if view is not None:
            await channel.send("", view=view)

        return curr_message.id

    async def edit_message(self, channel_id: int, message_id: int, new_content: str):
        channel = self.get_channel(channel_id)
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(content=new_content)
        except Exception as e:
            logging.exception(f"Could not edit message {message_id} in channel {channel_id}: {e}")

    async def add_reaction(self, channel_id: int, message_id: int, reaction: str):
        message = await (await self.fetch_channel(channel_id)).fetch_message(message_id)
        await message.add_reaction(reaction)

    def typing(self, channel_id: int):
        return self.get_channel(channel_id).typing()

    async def create_thread(self, parent_channel_id: int, title: str) -> int:
        # Create the private thread
        # Users/roles with "Manage Threads" will be able to see the private threads
        thread = await self.get_channel(parent_channel_id).create_thread(
            name=title,
            auto_archive_duration=60
        )
        return thread.id
