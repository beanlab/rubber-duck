import asyncio
import os
import re
from typing import TypedDict

from metrics import MetricsHandler
from feedback import FeedbackWorkflow

import argparse
import json
import logging

logging.basicConfig(level=logging.DEBUG)
from pathlib import Path

import discord

from rubber_duck import Message, RubberDuck, MessageHandler, Attachment
from quest import create_filesystem_manager
from bot_commands import BotCommands

LOG_FILE = Path('/tmp/duck.log')  # TODO - put a timestamp on this


def parse_blocks(text: str, limit=1990):
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


def get_feedback_workflow_id(thread_id):
    return f'feedback-{thread_id}'


class ChannelConfig(TypedDict):
    name: str | None
    id: int | None
    prompt: str | None
    prompt_file: str | None
    engine: str | None
    timeout: int | None


class RubberDuckConfig(TypedDict):
    command_channels: list[int]
    defaults: ChannelConfig
    channels: list[ChannelConfig]


class MyClient(discord.Client, MessageHandler):
    def __init__(self, config):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings
        intents.message_content = True
        super().__init__(intents=intents)

        feedback_config = config['feedback']
        quest_config = config['quest']
        metrics_config = config['metrics']
        self.admin_settings = config['admin_settings']
        open_ai_retry_protocol = config['open_ai_retry_protocol']
        rubber_duck_config = config['rubber_duck']

        # Command channel feature
        self._command_channel = self.admin_settings['admin_channel_id']

        # Rubber duck feature
        self._duck_channels = {
            (cc.get('name') or cc.get('id')): cc
            for cc in rubber_duck_config['channels']
        }
        self._defaults = rubber_duck_config['defaults']

        # MetricsHandler initialization
        self.metrics_handler = MetricsHandler(Path(metrics_config['metrics_path']))

        async def fetch_message(channel_id, message_id):
            return await (await self.fetch_channel(channel_id)).fetch_message(message_id)

        feedback_workflow = FeedbackWorkflow(
            self.send_message,
            fetch_message,
            self.metrics_handler.record_feedback
        )

        def create_workflow(wtype: str):
            match wtype:
                case 'command':
                    return BotCommands(self.send_message)

                case 'duck':

                    async def start_feedback_workflow(guild_id, channel_id, user_id):
                        if (server_feedback_config := feedback_config.get(str(guild_id))) is None:
                            return

                        workflow_id = get_feedback_workflow_id(channel_id)
                        self._workflow_manager.start_workflow(
                            'feedback', workflow_id, guild_id, channel_id, user_id,
                            server_feedback_config
                        )

                    return RubberDuck(self,
                                      self.metrics_handler,
                                      open_ai_retry_protocol,
                                      start_feedback_workflow
                                      )
                case 'feedback':
                    return feedback_workflow

            raise NotImplemented(f'No workflow of type {wtype}')

        self._workflow_manager = create_filesystem_manager(Path(quest_config['state_path']), 'rubber-duck', create_workflow)

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

        # ignore messages that start with //
        if message.content.startswith('//'):
            return

        # Command channel
        if message.channel.id == self._command_channel:
            self._workflow_manager.start_workflow(
                'command', str(message.id), as_message(message))
            return

        # Duck channel
        if message.channel.id in self._duck_channels:
            return await self.start_duck_conversation(
                self._defaults,
                self._duck_channels[message.channel.id],
                as_message(message)
            )

        if message.channel.name in self._duck_channels:
            return await self.start_duck_conversation(
                self._defaults,
                self._duck_channels[message.channel.name],
                as_message(message)
            )

        # Belongs to an existing conversation
        str_id = str(message.channel.id)
        if self._workflow_manager.has_workflow(str_id):
            await self._workflow_manager.send_event(
                str_id, 'messages', str_id, 'put',
                as_message(message)
            )

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.id == self.user.id:
            return
        message = reaction.message
        emoji = reaction.emoji

        # parse channel ID from message text
        # TODO - use quest workflow alias once implemented
        m = re.search(r'https://discord.com/channels/(\d+)/(\d+)/(\d+)', message.content)
        if m is None:
            return

        channel_id = m.group(2)
        workflow_id = get_feedback_workflow_id(channel_id)

        if self._workflow_manager.has_workflow(workflow_id):
            await self._workflow_manager.send_event(
                workflow_id, 'feedback', None, 'put',
                (emoji,user.id)
            )

    async def start_duck_conversation(self, defaults, config, message: Message):

        prompt = config.get('prompt', None)
        if prompt is None:
            prompt_file = config.get('prompt_file', None)
            if prompt_file is None:
                prompt = message['content']
            else:
                prompt = Path(prompt_file).read_text()

        engine = config.get('engine', defaults['engine'])

        timeout = config.get('timeout', defaults['timeout'])

        thread_id = await self.create_thread(
            message['channel_id'],
            message['content'][:20],
            message['author_id'],
            message['message_id'],
        )
        # await send message
        msg = await self.get_channel(message['channel_id']).fetch_message(
            message['message_id']
        )
        # Add reaction to original message to indicate to user
        #  that the message has been processed
        if "duck" in message['content'].lower():
            await msg.add_reaction('🦆')
        else:
            await msg.add_reaction('✅')

        await self.send_message(message["channel_id"],
                                f"<@{message['author_id']}> Click here to join the conversation: <#{thread_id}>")

        self._workflow_manager.start_workflow_background(
            'duck', str(thread_id), thread_id, engine, prompt, message, timeout
        )
        await asyncio.sleep(0.1)

    async def create_thread(self, parent_channel_id: int, title: str, author_id: int, message_id: int) -> int:
        # Create the private thread
        # Users/roles with "Manage Threads" will be able to see the private threads
        thread = await self.get_channel(parent_channel_id).create_thread(
            name=title,
            auto_archive_duration=60
        )

        # Grant access to the user
        await thread._state.http.add_user_to_thread(thread.id, author_id)
        msg = await self.get_channel(parent_channel_id).fetch_message(message_id)

        return thread.id

    #
    # Methods for MessageHandler protocol
    #

    async def send_message(self, channel_id, message: str, file=None, view=None) -> int:
        channel = self.get_channel(channel_id)
        curr_message = None
        if file is not None:
            file = discord.File(file)

        for block in parse_blocks(message):
            curr_message = await channel.send(block)

        if file is not None:
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

    async def report_error(self, msg: str, notify_admins: bool = False):
        if notify_admins:
            #TODO make this assume one id
            user_ids_to_mention = [self.admin_settings["admin_role_id"]]
            mentions = ' '.join([f'<@{user_id}>' for user_id in user_ids_to_mention])
            msg = mentions + '\n' + msg
            try:
                await self.send_message(self._command_channel, msg)
            except:
                logging.exception(f'Unable to message channel {self._command_channel}')

    def typing(self, channel_id):
        return self.get_channel(channel_id).typing()


def main(config):
    client = MyClient(config)
    client.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default='wiley_config_v2.json')
    parser.add_argument('--log-console', action='store_true')
    args = parser.parse_args()

    if args.log_console:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
        )

    else:
        logging.basicConfig(
            level=logging.DEBUG,
            filename=LOG_FILE,
            format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
        )

    config = json.loads(args.config.read_text())

    main(config)
