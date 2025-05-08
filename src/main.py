import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

import boto3
from quest import these
from quest.extras.sql import SqlBlobStorage

from .utils.logger import duck_logger
from .bot.discord_bot import DiscordBot
from .commands.bot_commands import BotCommands
from .commands.command import create_commands
from .conversation.conversation import BasicSetupConversation, HaveStandardGptConversation, HaveTAGradingConversation
from .conversation.threads import SetupPrivateThread
from .duck_orchestrator import DuckOrchestrator
from .metrics.feedback_manager import FeedbackManager
from .metrics.reporter import Reporter
from .rubber_duck_app import RubberDuckApp
from .storage.sql_connection import create_sql_session
from .storage.sql_metrics import SQLMetricsHandler
from .storage.sql_quest import create_sql_manager
from .utils.config_types import (
    Config, )
from .utils.gen_ai import OpenAI, RetryableGenAI
from .utils.persistent_queue import PersistentQueue


def fetch_config_from_s3() -> Config | None:
    # Initialize S3 client
    s3 = boto3.client('s3')

    # Add a section to your env file to allow for local and production environment
    environment = os.environ.get('ENVIRONMENT')
    if not environment or environment == 'LOCAL':
        duck_logger.info("Using local environment")
        return None

    # Get the S3 path from environment variables (CONFIG_FILE_S3_PATH should be set)
    s3_path = os.environ.get('CONFIG_FILE_S3_PATH')

    if not s3_path:
        duck_logger.warning("No S3 path configured")
        return None

    # Parse bucket name and key from the S3 path (s3://bucket-name/key)
    bucket_name, key = s3_path.replace('s3://', '').split('/', 1)
    duck_logger.info(f"Fetching config from bucket: {bucket_name}")
    duck_logger.info(f"Config key: {key}")

    try:
        # Download file from S3
        response = s3.get_object(Bucket=bucket_name, Key=key)

        # Read the content of the file and parse it as JSON
        config = json.loads(response['Body'].read().decode('utf-8'))
        duck_logger.info("Successfully loaded config from S3")
        return config

    except Exception as e:
        duck_logger.error(f"Failed to fetch config from S3: {e}")
        return None


# Function to load the configuration from a local file (if needed)
def load_local_config(file_path: Path) -> Config:
    duck_logger.info(f"Loading local config from {file_path}")
    return json.loads(file_path.read_text())


def setup_workflow_manager(duck_orchestrator, sql_session):
    workflows = {
        'duck-orchestrator': duck_orchestrator,
    }

    def create_workflow(wtype: str):
        if wtype in workflows:
            return workflows[wtype]

        raise NotImplementedError(f'No workflow of type {wtype}')

    namespace = 'rubber-duck'  # TODO - move to config.

    workflow_manager = create_sql_manager(namespace, create_workflow, sql_session)

    return workflow_manager


def setup_ducks(config: Config, bot: DiscordBot, sql_session, feedback_manager):
    # admin settings
    admin_settings = config['admin_settings']
    ai_completion_retry_protocol = config['ai_completion_retry_protocol']

    # Command channel feature
    command_channel = admin_settings['admin_channel_id']

    # SQLMetricsHandler initialization
    metrics_handler = SQLMetricsHandler(sql_session)

    # TODO - use this
    reporter = Reporter(metrics_handler, config['reporting'])  # TODO get the config to work with this

    setup_conversation = BasicSetupConversation(
        metrics_handler.record_message,
    )

    ai_client = OpenAI(
        os.environ['OPENAI_API_KEY'],
    )

    async def report_error(msg: str, notify_admins: bool = False):
        if notify_admins:
            user_ids_to_mention = [admin_settings["admin_role_id"]]
            mentions = ' '.join([f'<@{user_id}>' for user_id in user_ids_to_mention])
            msg = mentions + '\n' + msg
            try:
                await bot.send_message(command_channel, msg)
            except:
                duck_logger.exception(f'Unable to message channel {command_channel}')

    retryable_ai_client = RetryableGenAI(
        ai_client,
        bot.send_message,
        report_error,
        bot.typing,
        ai_completion_retry_protocol
    )

    have_conversation = HaveStandardGptConversation(
        retryable_ai_client,
        metrics_handler.record_message,
        metrics_handler.record_usage,
        bot.send_message,
        report_error,
        bot.typing,
        ai_completion_retry_protocol,
        setup_conversation
    )

    have_ta_conversation = HaveTAGradingConversation(
        metrics_handler.record_message,
        bot.send_message,
        report_error,
        bot.typing,
        feedback_manager
    )

    commands = create_commands(bot.send_message, metrics_handler, reporter)
    commands_workflow = BotCommands(commands, bot.send_message)

    return {
        'standard_conversation': have_conversation,
        'ta_grading_conversation': have_ta_conversation,
        'command': commands_workflow
    }


async def main(config: Config):
    sql_session = create_sql_session(config['sql'])

    async with DiscordBot() as bot:
        setup_thread = SetupPrivateThread(
            bot.create_thread,
            bot.send_message
        )

        queue_blob_storage = SqlBlobStorage('conversation-queues', sql_session)

        with these({
            channel_config['channel_id']: PersistentQueue(str(channel_config['channel_id']), queue_blob_storage)
            for server_config in config['servers'].values()
            for channel_config in server_config['channels']
            if 'feedback' in channel_config
        }) as persistent_queues:

            feedback_manager = FeedbackManager(persistent_queues)
            ducks = setup_ducks(config, bot, sql_session, feedback_manager)

            duck_orchestrator = DuckOrchestrator(
                setup_thread,
                ducks,
                feedback_manager.remember_conversation
            )

            channel_configs = {
                channel_config['channel_id']: channel_config
                for server_config in config['servers'].values()
                for channel_config in server_config['channels']
            }

            async with setup_workflow_manager(duck_orchestrator, sql_session) as workflow_manager:
                rubber_duck = RubberDuckApp(channel_configs, workflow_manager)
                bot.set_duck_app(rubber_duck, config['admin_settings']['admin_channel_id'])
                await bot.start(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default='config.json')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Set debug environment variable if debug flag is set
    if args.debug:
        duck_logger.setLevel(logging.DEBUG)
        from quest.utils import quest_logger
        quest_logger.setLevel(logging.DEBUG)
    else:
        duck_logger.setLevel(logging.INFO)
    # Try fetching the config from S3 first
    config = fetch_config_from_s3()

    if config is None:
        # If fetching from S3 failed, load from local file
        config = load_local_config(args.config)

    asyncio.run(main(config))
