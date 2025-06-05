import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import yaml  # Added import for YAML support

import boto3
from quest import these
from quest.extras.sql import SqlBlobStorage

from .armory.armory import Armory
from .armory.stat_tools import StatsTools
from .bot.discord_bot import DiscordBot
from .commands.bot_commands import BotCommands
from .commands.command import create_commands
from .conversation.conversation import BasicPromptConversation, BasicSetupConversation
from .conversation.threads import SetupPrivateThread
from .duck_orchestrator import DuckOrchestrator
from .metrics.feedback import HaveTAGradingConversation
from .metrics.feedback_manager import FeedbackManager
from .metrics.reporter import Reporter
from .rubber_duck_app import RubberDuckApp
from .storage.sql_connection import create_sql_session
from .storage.sql_metrics import SQLMetricsHandler
from .storage.sql_quest import create_sql_manager
from .utils.feedback_notifier import FeedbackNotifier
from .utils.config_types import Config
from .utils.data_store import DataStore
from .utils.gen_ai import OpenAI, RetryableGenAI
from .utils.logger import duck_logger
from .utils.persistent_queue import PersistentQueue
from .utils.send_email import EmailSender
from .workflows.registration_workflow import RegistrationWorkflow


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


def load_yaml_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def load_json_config(config_path):
    with open(config_path, 'r') as f:
        return json.load(f)

def load_local_config(config_path):
    if config_path.suffix == '.json':
        return load_json_config(config_path)
    elif config_path.suffix == '.yaml':
        return load_yaml_config(config_path)
    else:
        raise ValueError("Config file must be either .json or .yaml")


def setup_workflow_manager(config: Config, duck_orchestrator, sql_session, metrics_handler, send_message):
    reporter = Reporter(metrics_handler, config['reporting'])

    commands = create_commands(send_message, metrics_handler, reporter)
    commands_workflow = BotCommands(commands, send_message)

    workflows = {
        'duck-orchestrator': duck_orchestrator,
        'command': commands_workflow
    }

    def create_workflow(wtype: str):
        if wtype in workflows:
            return workflows[wtype]

        raise NotImplementedError(f'No workflow of type {wtype}')

    namespace = 'rubber-duck'  # TODO - move to config.

    workflow_manager = create_sql_manager(namespace, create_workflow, sql_session)

    return workflow_manager


def _has_workflow_of_type(config: Config, wtype: str):
    return any(
        duck['workflow_type'] == wtype
        for server_id, server_config in config['servers'].items()
        for channel_config in server_config['channels']
        for duck in channel_config['ducks']
    )


def setup_ducks(config: Config, bot: DiscordBot, metrics_handler, feedback_manager):
    ducks = {}
    if _has_workflow_of_type(config, 'basic_prompt_conversation'):
        armory = Armory()
        if 'dataset_folder_locations' in config:
            data_store = DataStore(config['dataset_folder_locations'])
            stat_tools = StatsTools(data_store)
            armory.scrub_tools(stat_tools)

        ai_client = OpenAI(
            os.environ['OPENAI_API_KEY'],
            armory,
            metrics_handler.record_usage
        )

        ai_completion_retry_protocol = config['ai_completion_retry_protocol']
        retryable_ai_client = RetryableGenAI(
            ai_client,
            bot.send_message,
            bot.report_error,
            bot.typing,
            ai_completion_retry_protocol
        )

        setup_conversation = BasicSetupConversation(
            metrics_handler.record_message,
        )

        have_conversation = BasicPromptConversation(
            retryable_ai_client,
            metrics_handler.record_message,
            metrics_handler.record_usage,
            bot.send_message,
            bot.report_error,
            bot.add_reaction,
            setup_conversation
        )
        ducks['basic_prompt_conversation'] = have_conversation

    if _has_workflow_of_type(config, 'conversation_review'):
        have_ta_conversation = HaveTAGradingConversation(
            feedback_manager,
            metrics_handler.record_feedback,
            bot.send_message,
            bot.add_reaction,
            bot.report_error
        )
        ducks['conversation_review'] = have_ta_conversation

    if _has_workflow_of_type(config, 'registration'):
        email_confirmation = EmailSender(config['sender_email'])

        registration_workflow = RegistrationWorkflow(
            bot.send_message,
            bot.get_channel,
            bot.fetch_guild,
            email_confirmation
        )
        ducks['registration'] = registration_workflow

    if not ducks:
        raise ValueError('No ducks were requested in the config')

    return ducks


async def main(config: Config):
    sql_session = create_sql_session(config['sql'])

    async with DiscordBot() as bot:
        setup_thread = SetupPrivateThread(
            bot.create_thread,
            bot.send_message
        )

        queue_blob_storage = SqlBlobStorage('conversation-queues', sql_session)

        convo_review_ducks = (
            duck
            for server_config in config['servers'].values()
            for channel_config in server_config['channels']
            for duck in channel_config['ducks']
            if duck['workflow_type'] == 'conversation_review'
        )

        target_channel_ids = (
            target_id
            for duck in convo_review_ducks
            for target_id in duck['settings']['target_channel_ids']
        )

        with these({
            target_id: PersistentQueue(str(target_id), queue_blob_storage)
            for target_id in target_channel_ids
        }) as persistent_queues:
            feedback_manager = FeedbackManager(persistent_queues)
            metrics_handler = SQLMetricsHandler(sql_session)

            ducks = setup_ducks(config, bot, metrics_handler, feedback_manager)

            duck_orchestrator = DuckOrchestrator(
                setup_thread,
                bot.send_message,
                bot.report_error,
                ducks,
                feedback_manager.remember_conversation
            )

            channel_configs = {
                channel_config['channel_id']: channel_config
                for server_config in config['servers'].values()
                for channel_config in server_config['channels']
            }

            async with setup_workflow_manager(
                    config,
                    duck_orchestrator,
                    sql_session,
                    metrics_handler,
                    bot.send_message
            ) as workflow_manager:
                admin_channel_id = config['admin_settings']['admin_channel_id']
                rubber_duck = RubberDuckApp(
                    admin_channel_id,
                    channel_configs,
                    workflow_manager
                )
                bot.set_duck_app(rubber_duck, admin_channel_id)

                # Set up the notifier thread.
                notifier = FeedbackNotifier(feedback_manager, bot.send_message, config['servers'].values(), config['feedback_notifier_settings'])
                await asyncio.gather(
                    bot.start(os.environ['DISCORD_TOKEN']),
                    notifier.start()
                )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default='config.json', help='Path to config file (.json or .yaml)')
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
