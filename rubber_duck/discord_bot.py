import argparse
import json
import logging
import os
from pathlib import Path
from typing import TypedDict

import boto3
import discord
from quest import wrap_steps

from sql_quest import create_sql_manager
from bot_commands import BotCommands
from command import UsageMetricsCommand, MessagesMetricsCommand, FeedbackMetricsCommand, MetricsCommand, StatusCommand, \
    ReportCommand, BashExecuteCommand, LogCommand, Command, ActiveWorkflowsCommand
from conversation import HaveStandardGptConversation, BasicSetupConversation, RetryableGenAIClient
from feedback import GetTAFeedback, GetConvoFeedback
from genAI import OpenAI, RetryableGenAI
from protocols import Attachment, Message
from reporter import Reporter
from rubber_duck import RubberDuck
from sql_metrics import SQLMetricsHandler
from sql_connection import create_sql_session
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


class MyClient(discord.Client):
    def __init__(self, config):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings
        intents.message_content = True
        super().__init__(intents=intents)

        self.admin_settings = config['admin_settings']
        ai_completion_retry_protocol = config['ai_completion_retry_protocol']

        # Command channel feature
        self._command_channel = self.admin_settings['admin_channel_id']

        # Rubber duck feature
        self._duck_config = config['rubber_duck']
        self._duck_channels = set(conf.get('channel_name') or conf.get('channel_id') for conf in self._duck_config['channels'])

        # SQLMetricsHandler initialization
        sql_session = create_sql_session(config['sql'])
        self.metrics_handler = SQLMetricsHandler(sql_session)
        wrap_steps(self.metrics_handler, ["record_message", "record_usage", "record_feedback"])

        reporter = Reporter(self.metrics_handler, config['reporting'])

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

        setup_conversation = BasicSetupConversation(
            self.metrics_handler.record_message,
        )

        ai_client = OpenAI(
            os.environ['OPENAI_API_KEY'],
        )

        retryable_ai_client = RetryableGenAI(
            ai_client,
            self.send_message,
            self.report_error,
            self.typing,
            ai_completion_retry_protocol
        )

        wrap_steps(ai_client, ['get_completion'])
#
        have_conversation = HaveStandardGptConversation(
            retryable_ai_client,
            self.metrics_handler.record_message,
            self.metrics_handler.record_usage,
            self.send_message,
            self.report_error,
            self.typing,
            ai_completion_retry_protocol,
        )

        duck_workflow = RubberDuck(
            self._duck_config,
            setup_thread,
            setup_conversation,
            have_conversation,
            get_feedback,
        )
        workflows = {
            'duck': duck_workflow
        }

        def create_workflow(wtype: str):
            if wtype in workflows:
                return workflows[wtype]

            raise NotImplementedError(f'No workflow of type {wtype}')

        namespace = 'rubber-duck'  # TODO - move to config
        self._workflow_manager = create_sql_manager(namespace, create_workflow, sql_session)

        commands = create_commands(self.send_message, self.metrics_handler, reporter, self._workflow_manager.get_workflow_metrics)
        commands_workflow = BotCommands(commands, self.send_message)

        workflows['command'] = commands_workflow

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
            self._workflow_manager.start_workflow(
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
            self._workflow_manager.start_workflow(
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
        if channel is None:
            await self.report_error(f'Tried to send message on {channel_id}, but no channel found.')
            raise Exception(f'No channel id {channel_id}')

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


def fetch_config_from_s3():
    # Initialize S3 client
    s3 = boto3.client('s3')
    
    # Add a section to your env file to allow for local and production environment
    environment = os.environ.get('ENVIRONMENT')
    if not environment or environment == 'LOCAL':
        return None
    
    # Get the S3 path from environment variables (CONFIG_FILE_S3_PATH should be set)
    s3_path = os.environ.get('CONFIG_FILE_S3_PATH')

    if not s3_path:
        return None

    # Parse bucket name and key from the S3 path (s3://bucket-name/key)
    bucket_name, key = s3_path.replace('s3://', '').split('/', 1)
    logging.info(bucket_name)
    logging.info(key)
    try:
        # Download file from S3
        response = s3.get_object(Bucket=bucket_name, Key=key)

        # Read the content of the file and parse it as JSON
        config = json.loads(response['Body'].read().decode('utf-8'))
        return config

    except Exception as e:
        print(f"Failed to fetch config from S3: {e}")
        return None


# Function to load the configuration from a local file (if needed)
def load_local_config(file_path: Path):
    return json.loads(file_path.read_text())


def main(config):
    client = MyClient(config)
    client.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default='config.json')
    parser.add_argument('--log-console', action='store_true')
    args = parser.parse_args()

    # Set up logging based on user preference
    if args.log_console:
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            filename='logfile.log',  # Replace LOG_FILE with the actual log file path
            format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
        )

    # Try fetching the config from S3 first
    config = fetch_config_from_s3()

    if config is None:
        # If fetching from S3 failed, load from local file
        config = load_local_config(args.config)
    main(config)
