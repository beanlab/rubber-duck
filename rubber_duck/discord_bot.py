import argparse
import json
import logging
import os
from pathlib import Path
from typing import TypedDict

import discord
from quest import wrap_steps

from SQLquest import create_sql_manager
from bot_commands import BotCommands
from conversation import HaveStandardGptConversation
from feedback import GetTAFeedback, GetConvoFeedback
from protocols import Attachment, Message
from reporter import Reporter
from rubber_duck import RubberDuck
from sql_metrics import SQLMetricsHandler
from sqlite import create_sqlite_session
from threads import SetupPrivateThread

logging.basicConfig(level=logging.INFO)
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


# noinspection PyBroadException
class MyClient(discord.Client):
    def __init__(self, config):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings
        intents.message_content = True
        super().__init__(intents=intents)

        self.admin_settings = config['admin_settings']
        open_ai_retry_protocol = config['open_ai_retry_protocol']

        # Command channel feature
        self._command_channel = self.admin_settings['admin_channel_id']

        # Rubber duck feature
        self._duck_config = config['rubber_duck']
        self._duck_channels = set(conf.get('name') or conf.get('id') for conf in self._duck_config['channels'])

        # SQLMetricsHandler initialization
        db_url = config["sql"]["db_url"]
        sql_session = create_sqlite_session(db_url)
        self.metrics_handler = SQLMetricsHandler(sql_session)
        wrap_steps(self.metrics_handler, ["record_message", "record_usage", "record_feedback"])

        reporter = Reporter(self.metrics_handler, config['reporting'])
        commands_workflow = BotCommands(self.send_message, self.metrics_handler, reporter)

        # Feedback
        get_ta_feedback = GetTAFeedback(
            self.send_message,
            self.add_reaction,
            self.metrics_handler.record_feedback,
        )

        feedback_configs = config['feedback']

        get_feedback = GetConvoFeedback(
            feedback_configs,
            get_ta_feedback
        )

        setup_thread = SetupPrivateThread(
            self.create_thread,
            self.send_message
        )

        have_conversation = HaveStandardGptConversation(
            os.environ['OPENAI_API_KEY'],
            open_ai_retry_protocol,
            self.metrics_handler.record_message,
            self.metrics_handler.record_usage,
            self.send_message,
            self.report_error,
            self.typing
        )

        duck_workflow = RubberDuck(
            self._duck_config,
            setup_thread,
            have_conversation,
            get_feedback,
        )

        def create_workflow(wtype: str):
            match wtype:
                case 'command':
                    return commands_workflow

                case 'duck':
                    return duck_workflow

            raise NotImplementedError(f'No workflow of type {wtype}')

        namespace = 'rubber-duck'  # TODO - move to config
        self._workflow_manager = create_sql_manager(namespace, create_workflow, sql_session)

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
            workflow_id = f'command-{message.id}'
            self._workflow_manager.start_workflow_background(
                'command', workflow_id, as_message(message))
            return

        # Duck channel
        channel_name = None
        if message.channel.id in self._duck_channels:
            channel_name = message.channel.id
        elif message.channel.name in self._duck_channels:
            channel_name = message.channel.name

        if channel_name is not None:
            workflow_id = f'duck-{message.id}'
            self._workflow_manager.start_workflow_background(
                'duck', workflow_id, channel_name, as_message(message)
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
        curr_message = None

        for block in parse_blocks(message):
            curr_message = await channel.send(block)

        if file is not None:
            if isinstance(file, list):
                curr_message = await channel.send("",
                                                  files=file)  # TODO: check that all instances are discord.File objects
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
            # TODO make this assume one id
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


def main(config):
    client = MyClient(config)
    client.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default='config.json')
    parser.add_argument('--log-console', action='store_true')
    args = parser.parse_args()

    if args.log_console:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            filename='logfile.log',  # Replace LOG_FILE with the actual log file path
            format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
        )

    try:
        if args.config.is_file():
            app_config = json.loads(args.config.read_text())
        else:
            default_config_path = Path('config.json')
            if default_config_path.is_file():
                app_config = json.loads(default_config_path.read_text())
            else:
                raise FileNotFoundError(default_config_path)

    except FileNotFoundError as fnf:
        print(f"No valid config file found: {fnf}. Please create a config.json or use the default template.")
        print("You can find the default config template here: "
              "https://github.com/beanlab/rubber-duck/blob/master/config.json")
        print("For detailed instructions, check the README here: link_to_readme")
        exit(1)

    main(app_config)
