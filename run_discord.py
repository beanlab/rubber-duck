"""Entry point for the Discord adapter.

Usage:
    python run_discord.py --config path/to/config.yaml [--debug] [--log-path /logs]

Required environment variables:
    DISCORD_TOKEN  Bot token from the Discord Developer Portal

Optional environment variables:
    CONFIG_FILE_S3_PATH  Config URI fallback when --config is not supplied

A .env file in the working directory is loaded automatically if present.
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path

from quest import these
from quest.utils import quest_logger

from src.bot.discord_bot import DiscordBot
from src.conversation.threads import SetupPrivateThread
from src.duck_orchestrator import DuckOrchestrator
from src.gen_ai.gen_ai import AIClient
from src.main import (
    _build_feedback_queues,
    _setup_cache_cleaner,
    _setup_ducks,
    add_agent_tools_to_armory,
    build_armory,
    setup_workflow_manager,
)
from src.metrics.feedback_manager import FeedbackManager
from src.rubber_duck_app import RubberDuckApp
from src.storage.sql_connection import create_sql_session
from src.storage.sql_metrics import SQLMetricsHandler
from src.utils.config_loader import load_configuration
from src.utils.config_types import Config
from src.utils.feedback_notifier import FeedbackNotifier
from src.utils.logger import add_console_handler, add_file_handler, duck_logger, filter_logs
from src.utils.python_exec_container import build_containers

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


async def _main_discord(config: Config, log_dir: Path | None) -> None:
    sql_session = create_sql_session(config['sql'])

    async with DiscordBot() as bot:
        setup_thread = SetupPrivateThread(bot.create_thread, bot.send_message)
        filter_logs(bot.send_message, config['admin_settings'])

        with _build_feedback_queues(config, sql_session) as persistent_queues:
            feedback_manager = FeedbackManager(persistent_queues)
            metrics_handler = SQLMetricsHandler(sql_session)

            with these(build_containers(config)) as containers:
                armory, talk_tool, tool_caches = build_armory(
                    config, bot.send_message, containers, sql_session
                )
                ai_client = AIClient(
                    armory, bot.typing,
                    metrics_handler.record_message, metrics_handler.record_usage,
                )
                add_agent_tools_to_armory(config, armory, ai_client)

                ducks = _setup_ducks(
                    config, bot, metrics_handler, feedback_manager, ai_client, armory, talk_tool,
                )

                duck_orchestrator = DuckOrchestrator(
                    setup_thread,
                    bot.send_message,
                    bot.add_reaction,
                    ducks,
                    feedback_manager.remember_conversation,
                )

                channel_configs = {
                    channel_config['channel_id']: channel_config
                    for server_config in config['servers'].values()
                    for channel_config in server_config['channels'].values()
                }

                async with setup_workflow_manager(
                    config, duck_orchestrator, sql_session, metrics_handler,
                    bot.send_message, log_dir, tool_caches,
                ) as workflow_manager:
                    admin_channel_id = config['admin_settings']['admin_channel_id']
                    rubber_duck = RubberDuckApp(admin_channel_id, channel_configs, workflow_manager)
                    bot.set_duck_app(rubber_duck, admin_channel_id)

                    tasks = [bot.start(os.environ['DISCORD_TOKEN'])]

                    if 'feedback_notifier_settings' in config:
                        notifier = FeedbackNotifier(
                            feedback_manager,
                            bot.send_message,
                            config['servers'].values(),
                            config['feedback_notifier_settings'],
                        )
                        tasks.append(notifier.start())
                    if tool_caches:
                        cleaner = _setup_cache_cleaner(tool_caches, config.get("cache", {}))
                        tasks.append(cleaner.start())

                    await asyncio.gather(*tasks)


async def main(config: Config, log_dir: Path | None) -> None:
    try:
        await _main_discord(config, log_dir)
    except Exception as ex:
        duck_logger.exception('ERROR in MAIN')
        print(ex)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start the Discord rubber-duck bot')
    parser.add_argument(
        '--config', type=str,
        help='Path to config file (.json or .yaml, or s3://...)',
    )
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--log-path', type=Path, help='Set the log path for the duck logger')

    args = parser.parse_args()

    if args.debug:
        duck_logger.setLevel(logging.DEBUG)
        quest_logger.setLevel(logging.DEBUG)
    else:
        duck_logger.setLevel(logging.INFO)
        quest_logger.setLevel(logging.INFO)

    if args.log_path:
        add_file_handler(args.log_path)
    else:
        duck_logger.warning('No log path provided. Logging to console only.')

    add_console_handler()

    if args.config is None:
        args.config = os.getenv('CONFIG_FILE_S3_PATH')

    config: Config = load_configuration(args.config)

    asyncio.run(main(config, args.log_path))
