import asyncio
import os
from typing import TypedDict

from metrics import MetricsHandler


def load_env():
    with open('secrets.env') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            key, value = line.split('=')
            os.environ[key] = value


load_env()

import argparse
import json
import logging
logging.basicConfig(level=logging.DEBUG)
from pathlib import Path

import discord

from rubber_duck import Message, RubberDuck, MessageHandler, ErrorHandler
from quest import create_filesystem_manager
from bot_commands import BotCommands

LOG_FILE = Path('/tmp/duck.log')  # TODO - put a timestamp on this


def parse_blocks(text: str, limit=2000):
    tick = '`'
    block = ""
    current_fence = ""
    for line in text.splitlines():
        if len(block) + len(line) > limit - 3:
            if block:
                if current_fence:
                    block += '```'
                yield block
                block = current_fence

        block += ('\n' + line) if block else line

        if line.strip().startswith(tick * 3):
            if current_fence:
                current_fence = ""
            else:
                current_fence = line

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
        is_file=len(message.attachments) > 0
    )


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
    def __init__(self, root_save_folder: Path, config: RubberDuckConfig):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings
        intents.message_content = True
        super().__init__(intents=intents)

        # root_state_folder: Path,
        #                  log_file_path: Path,
        #                  configs: list[dict]
        #

        self._config = config
        self._duck_channels = {
            (cc.get('name') or cc.get('id')): cc
            for cc in config['channels']
        }

        state_folder = root_save_folder / 'history'
        metrics_folder = root_save_folder / 'metrics'

        def create_workflow(wtype: str):
            match wtype:
                case 'command':
                    return BotCommands(self.send_message)
                case 'duck':
                    return RubberDuck(self.handle_error, self, MetricsHandler(metrics_folder))

            raise NotImplemented(f'No workflow of type {wtype}')

        self._workflow_manager = create_filesystem_manager(state_folder, 'rubber-duck', create_workflow)

    async def on_ready(self):
        # print out information when the bot wakes up
        logging.info('Logged in as')
        logging.info(self.user.name)
        logging.info(self.user.id)
        logging.info('Starting workflow manager')
        self._workflow_manager = await self._workflow_manager.__aenter__()
        await asyncio.sleep(0.1)
        logging.info('Workflow manager ready')

        for channel_id in self._config['command_channels']:
            try:
                await self.send_message(channel_id, 'Duck online')
            except:
                logging.exception(f'Unable to message channel {channel_id}')

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
        if message.channel.id in self._config['command_channels']:
            self._workflow_manager.start_workflow(
                'command', str(message.id), as_message(message))
            return

        # Duck channel
        if message.channel.id in self._duck_channels:
            return await self.start_duck_conversation(
                self._config['defaults'],
                self._duck_channels[message.channel.id],
                as_message(message)
            )

        if message.channel.name in self._duck_channels:
            return await self.start_duck_conversation(
                self._config['defaults'],
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

        # Ignore message

    async def start_duck_conversation(self, defaults, config, message: Message):
        thread_id = await self.create_thread(
            message['channel_id'],
            message['content'][:20],
            message['author_id'],
            message['message_id']
        )
        prompt = config.get('prompt', None)
        if prompt is None:
            prompt_file = config.get('prompt_file', None)
            if prompt_file is None:
                prompt = message['content']
            else:
                prompt = Path(prompt_file).read_text()

        engine = config.get('engine', defaults['engine'])

        timeout = config.get('timeout', defaults['timeout'])

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

        # Add reaction to original message to indicate to user
        #  that the message has been processed
        msg = await self.get_channel(parent_channel_id).fetch_message(message_id)
        if 'duck' in title.lower():
            await msg.add_reaction('🦆')
        else:
            await msg.add_reaction('✅')

        return thread.id

    #
    # Methods for MessageHandler protocol
    #

    async def send_message(self, channel_id, message: str, file=None):
        if file is not None:
            file = discord.File(file)

        for block in parse_blocks(message):
            await self.get_channel(channel_id).send(block)

        if file is not None:
            await self.get_channel(channel_id).send("", file=file)

    def typing(self, channel_id):
        return self.get_channel(channel_id).typing()

    #
    # Method for ErrorHandler Protocol
    #
    async def handle_error(self, msg: str):
        for channel_id in self._config['command_channels']:
            try:
                await self.send_message(channel_id, msg)
            except:
                logging.exception(f'Unable to message channel {channel_id}')

def main(state_path: Path, config: RubberDuckConfig):
    client = MyClient(state_path, config)
    client.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default='config.json')
    parser.add_argument('--state', type=Path, default='state')
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

    main(args.state, config)
