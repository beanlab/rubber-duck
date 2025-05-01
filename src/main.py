import argparse
import json
import logging
import os
from pathlib import Path
import boto3
from utils.config_types import (
    Config, FeedbackConfig,
)
from metrics.reporter import Reporter
from rubber_duck_app import RubberDuckApp
from storage.sql_connection import create_sql_session
from storage.sql_metrics import SQLMetricsHandler
from metrics.feedback import GetTAFeedback, GetConvoFeedback
from bot.discord_bot import DiscordBot, create_commands
from commands.bot_commands import BotCommands
from conversation.conversation import BasicSetupConversation, HaveStandardGptConversation
from utils.gen_ai import OpenAI, RetryableGenAI
from workflows.basic_prompt_workflow import BasicPromptWorkflow
from storage.sql_quest import create_sql_manager
from conversation.threads import SetupPrivateThread

logging.basicConfig(level=logging.INFO)
LOG_FILE = Path('/tmp/duck.log')  # TODO - put a timestamp on this. Is this really needed?


def fetch_config_from_s3() -> Config | None:
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
def load_local_config(file_path: Path) -> Config:
    return json.loads(file_path.read_text())


def setup_workflow_manager(config: Config, bot: DiscordBot):
    # admin settings
    admin_settings = config['admin_settings']
    ai_completion_retry_protocol = config['ai_completion_retry_protocol']

    # Command channel feature
    command_channel = admin_settings['admin_channel_id']

    # Convert config to typed dictionaries
    server_config = config['servers']
    default_duck_workflow_config = config['default_duck_settings']

    # SQLMetricsHandler initialization
    sql_session = create_sql_session(config['sql'])
    metrics_handler = SQLMetricsHandler(sql_session)

    reporter = Reporter(metrics_handler, config['reporting'])  # TODO get the config to work with this

    # Feedback
    get_ta_feedback = GetTAFeedback(
        bot.send_message,
        bot.add_reaction,
        metrics_handler.record_feedback,
    )

    feedback_config: dict[int, FeedbackConfig] = {
        channel["channel_id"]: channel["feedback"]
        for server in server_config.values()
        for channel in server["channels"]
    }

    get_feedback = GetConvoFeedback(
        feedback_config,
        get_ta_feedback
    )
    # TODO: remove weights from config
    setup_thread = SetupPrivateThread(
        bot.create_thread,
        bot.send_message
    )

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
                logging.exception(f'Unable to message channel {command_channel}')

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
    )

    duck_workflow = BasicPromptWorkflow(
        server_config,
        default_duck_workflow_config,
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

    namespace = 'rubber-duck'  # TODO - move to config.
    workflow_manager = create_sql_manager(namespace, create_workflow, sql_session)

    commands = create_commands(bot.send_message, metrics_handler, reporter,
                               workflow_manager.get_workflow_metrics)
    commands_workflow = BotCommands(commands, bot.send_message)

    workflows['command'] = commands_workflow

    return workflow_manager


async def main(config):
    async with DiscordBot() as bot, \
            setup_workflow_manager(config, bot) as workflow_manager:
        rubber_duck = RubberDuckApp(config['servers'], config['admin_settings']['admin_channel_id'], workflow_manager)
        bot.set_duck_app(rubber_duck)
        await bot.start(os.environ['DISCORD_TOKEN'])


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
    
    import asyncio
    asyncio.run(main(config))
