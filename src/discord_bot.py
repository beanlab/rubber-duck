import logging
import discord
from command import UsageMetricsCommand, MessagesMetricsCommand, FeedbackMetricsCommand, MetricsCommand, StatusCommand, \
    ReportCommand, BashExecuteCommand, LogCommand, Command, ActiveWorkflowsCommand
from protocols import Attachment, Message
from config_types import (
    Config,
)


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
        self._workflow_manager = await self._workflow_manager.__aenter__()

        try:
            await self.send_message(self._command_channel, 'Duck online')
        except:
            logging.exception(f'Unable to message channel {self._command_channel}')

        logging.info('------')

    async def close(self):
        logging.warning("-- Suspending --")
        await self._workflow_manager.__aexit__(None, None, None)
        await super().close()

    async def on_message(self, message: discord.Message):
        # ignore messages from the bot itself
        if message.author.id == self.user.id:
            return

        # ignore messages from other bots
        if message.author.bot:
            return

        # ignore messages that start with //
        if message.content.startswith('//'):
            return

        # Command channel
        if message.channel.id == self._command_channel:
            workflow_id = f'command-{message.id}'
            self._workflow_manager.start_workflow(
                'command', workflow_id, as_message(message))
            return

        # Duck channel
        if message.channel.id in self._duck_channels:
            workflow_id = f'duck-{message.channel.id}-{message.id}'
            self._workflow_manager.start_workflow(
                'duck',
                workflow_id,
                message.channel.id,
                as_message(message)
            )

        # Belongs to an existing conversation
        str_id = str(message.channel.id)
        if self._workflow_manager.has_workflow(str_id):
            await self._workflow_manager.send_event(
                str_id, 'messages', None, 'put',
                as_message(message)
            )

        # If it didn't match anything above, we can ignore it.

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        # Ignore messages from the bot
        if user.id == self.user.id:
            return

        workflow_alias = str(reaction.message.id)
        emoji = reaction.emoji

        if self._workflow_manager.has_workflow(workflow_alias):
            await self._workflow_manager.send_event(
                workflow_alias, 'feedback', None, 'put',
                (emoji, user.id)
            )

    #
    # Methods for message-handling protocols
    #

    async def send_message(self, channel_id, message: str, file=None, view=None) -> int:
        channel = self.get_channel(channel_id)
        if channel is None:
            await self.report_error(f'Tried to send message on {channel_id}, but no channel found.')
            raise Exception(f'No channel id {channel_id}')

        curr_message = None

        for block in _parse_blocks(message):
            curr_message = await channel.send(block)

        if file is not None:
            if isinstance(file, list):
                curr_message = await channel.send("",
                                                  files=file)  # TODO: check that all instances are discord.File objects.
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

    async def report_error(self, msg: str, notify_admins: bool = False):
        if notify_admins:
            user_ids_to_mention = [self.admin_settings["admin_role_id"]]
            mentions = ' '.join([f'<@{user_id}>' for user_id in user_ids_to_mention])
            msg = mentions + '\n' + msg
            try:
                await self.send_message(self._command_channel, msg)
            except:
                logging.exception(f'Unable to message channel {self._command_channel}')

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
