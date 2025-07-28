import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Iterable

from quest import these
from quest.extras.sql import SqlBlobStorage
from quest.utils import quest_logger

from .bot.discord_bot import DiscordBot
from .commands.bot_commands import BotCommands
from .commands.command import create_commands
from .conversation.threads import SetupPrivateThread
from .duck_orchestrator import DuckOrchestrator, DuckConversation
from .gen_ai.build import build_agent_conversation_duck
from .metrics.feedback import HaveTAGradingConversation, ConversationReviewSettings
from .metrics.feedback_manager import FeedbackManager, CHANNEL_ID
from .metrics.reporter import Reporter
from .rubber_duck_app import RubberDuckApp
from .storage.sql_connection import create_sql_session
from .storage.sql_metrics import SQLMetricsHandler
from .storage.sql_quest import create_sql_manager
from .utils.config_loader import load_configuration
from .utils.config_types import Config, RegistrationSettings, DUCK_WEIGHT, \
    DUCK_NAME, DuckConfig
from .utils.feedback_notifier import FeedbackNotifier
from .utils.logger import duck_logger, filter_logs, add_console_handler
from .utils.persistent_queue import PersistentQueue
from .utils.send_email import EmailSender
from .workflows.registration_workflow import RegistrationWorkflow



def setup_workflow_manager(
        config: Config,
        duck_orchestrator,
        sql_session,
        metrics_handler,
        send_message,
        log_dir: Path
):
    reporter = Reporter(metrics_handler, config['servers'], config['reporter_settings'], True)

    commands = create_commands(send_message, metrics_handler, reporter, log_dir)
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


def build_conversation_review_duck(
        name: str,
        settings: ConversationReviewSettings,
        bot: DiscordBot, record_feedback, feedback_manager
) -> DuckConversation:
    have_ta_conversation = HaveTAGradingConversation(
        name,
        settings,
        feedback_manager,
        record_feedback,
        bot.send_message,
        bot.add_reaction,
    )
    return have_ta_conversation


def build_registration_duck(
        name: str, bot: DiscordBot, config: Config, settings: RegistrationSettings
):
    email_confirmation = EmailSender(config['sender_email'])

    registration_workflow = RegistrationWorkflow(
        name,
        bot.send_message,
        bot.get_channel,
        bot.fetch_guild,
        email_confirmation,
        settings
    )
    return registration_workflow


def _iterate_duck_configs(config: Config) -> Iterable[DuckConfig]:
    # Look for global configs
    yield from config['ducks']

    # Look for inline duck configs
    for server_config in config['servers'].values():
        for channel_config in server_config['channels']:
            if not isinstance(channel_config.get('ducks'), list):
                duck_logger.error(f"Channel {channel_config.get('channel_id')} has invalid ducks: {channel_config.get('ducks')}")
            for item in channel_config.get('ducks') or []:
                if isinstance(item, DUCK_NAME):
                    continue
                elif isinstance(item, dict):
                    if 'weight' in item:
                        duck = item['duck']
                        if isinstance(duck, DUCK_NAME):
                            continue
                        yield duck
                    else:
                        yield item


def build_ducks(
        config: Config,
        bot: DiscordBot,
        metrics_handler,
        feedback_manager,
) -> dict[DUCK_NAME, DuckConversation]:
    ducks = {}

    for duck_config in _iterate_duck_configs(config):
        duck_type = duck_config['duck_type']
        settings = duck_config['settings']
        name = duck_config['name']

        if duck_type == 'agent_conversation':
            ducks[name] = build_agent_conversation_duck(
                name, config, settings, bot, metrics_handler.record_message, metrics_handler.record_usage
            )

        elif duck_type == 'conversation_review':
            ducks[name] = build_conversation_review_duck(
                name, settings, bot, metrics_handler.record_feedback, feedback_manager
            )

        elif duck_type == 'registration':
            ducks[name] = build_registration_duck(name, bot, config, settings)

        else:
            raise NotImplementedError(f'Duck of type {duck_type} not implemented')

    if not ducks:
        raise ValueError('No ducks were requested in the config')

    return ducks


def _setup_ducks(
        config: Config,
        bot: DiscordBot,
        metrics_handler,
        feedback_manager,
) -> dict[CHANNEL_ID, list[tuple[DUCK_WEIGHT, DuckConversation]]]:
    """
    Return a dictionary of channel ID to list of weighted ducks
    """
    all_ducks = build_ducks(config, bot, metrics_handler, feedback_manager)

    channel_ducks = {}

    for server_config in config['servers'].values():
        for channel_config in server_config['channels']:
            channel_ducks[channel_config['channel_id']] = []
            for duck_config in channel_config['ducks']:
                if isinstance(duck_config, str):
                    name, weight = duck_config, 1

                elif isinstance(duck_config, dict) and 'weight' in duck_config:
                    name = duck_config['name']
                    weight = duck_config['weight']

                elif isinstance(duck_config, dict):
                    name, weight = duck_config['name'], 1

                else:
                    raise ValueError(f'Incorrect format for duck config: {channel_config["channel_id"]}')

                channel_ducks[channel_config['channel_id']].append((weight, all_ducks[name]))

    return channel_ducks


def _build_feedback_queues(config: Config, sql_session):
    queue_blob_storage = SqlBlobStorage('conversation-queues', sql_session)

    convo_review_ducks = (
        duck
        for duck in _iterate_duck_configs(config)
        if duck['duck_type'] == 'conversation_review'
    )

    target_channel_ids = (
        target_id
        for duck in convo_review_ducks
        for target_id in duck['settings']['target_channel_ids']
    )

    return these({
        target_id: PersistentQueue(str(target_id), queue_blob_storage)
        for target_id in target_channel_ids
    })


async def main(config: Config, log_dir: Path):
    sql_session = create_sql_session(config['sql'])

    async with DiscordBot() as bot:
        setup_thread = SetupPrivateThread(
            bot.create_thread,
            bot.send_message
        )

        filter_logs(bot.send_message, config['admin_settings'])

        with _build_feedback_queues(config, sql_session) as persistent_queues:
            feedback_manager = FeedbackManager(persistent_queues)
            metrics_handler = SQLMetricsHandler(sql_session)

            ducks = _setup_ducks(config, bot, metrics_handler, feedback_manager)

            duck_orchestrator = DuckOrchestrator(
                setup_thread,
                bot.send_message,
                bot.add_reaction,
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
                    bot.send_message,
                    log_dir
            ) as workflow_manager:
                tasks = []

                admin_channel_id = config['admin_settings']['admin_channel_id']
                rubber_duck = RubberDuckApp(
                    admin_channel_id,
                    channel_configs,
                    workflow_manager
                )
                bot.set_duck_app(rubber_duck, admin_channel_id)
                tasks.append(bot.start(os.environ['DISCORD_TOKEN']))

                if 'feedback_notifier_settings' in config:
                    # Set up the notifier thread.
                    notifier = FeedbackNotifier(feedback_manager, bot.send_message, config['servers'].values(),
                                                config['feedback_notifier_settings'])
                    tasks.append(notifier.start())

                await asyncio.gather(*tasks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, help='Path to config file (.json or .yaml, or s3://...)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--log-path', type=Path, help='Set the log path for the duck logger')

    args = parser.parse_args()

    # Set debug environment variable if debug flag is set
    if args.debug:
        duck_logger.setLevel(logging.DEBUG)
        # quest_logger.setLevel(logging.DEBUG)
    else:
        duck_logger.setLevel(logging.INFO)
        quest_logger.setLevel(logging.INFO)

    if args.log_path:
        # Add a file handler to the duck logger if log path is provided
        from .utils.logger import add_file_handler

        log_dir = add_file_handler(args.log_path)
    else:
        duck_logger.warn("No log path provided. Logging to console only.")

    # Add console handler to the duck logger
    add_console_handler()

    config: Config = load_configuration(args.config)

    asyncio.run(main(config, args.log_path))
