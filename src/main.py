import argparse
import asyncio
import logging
import os
from importlib import import_module
from pathlib import Path

from dotenv import load_dotenv
from quest import these
from quest.utils import quest_logger

from .bot.discord_bot import DiscordBot
from .commands.bot_commands import BotCommands
from .commands.command import create_commands
from .conversation.threads import SetupPrivateThread
from .duck_orchestrator import DuckOrchestrator
from .duck_protocols import DuckBuilder, DuckConversation, MessageHandler, MetricsHandler
from .gen_ai.ai_responses import ResponsesAPI
from .metrics.feedback_manager import FeedbackManager
from .metrics.reporter import Reporter
from .rubber_duck_app import RubberDuckApp
from .storage.serializer import workflow_serializer
from .storage.sql_connection import create_sql_session
from .storage.sql_metrics import SQLMetricsHandler
from .storage.sql_quest import create_sql_manager
from .utils.cache_cleaner import CacheCleaner
from .utils.config_loader import load_configuration
from .utils.config_types import CHANNEL_ID, Config
from .utils.logger import add_console_handler, add_file_handler, duck_logger, filter_logs
from .utils.protocols import ToolCache
from .utils.python_exec_container import build_containers


def iter_channels(config: Config):
    for server in config["servers"].values():
        yield from server["channels"].values()


def build_ducks(
        config: Config,
        *,
        message_handler: MessageHandler,
        metrics_handler: MetricsHandler,
        responses_api: ResponsesAPI,
        containers: dict,
        sql_session,
) -> dict[CHANNEL_ID, DuckConversation]:
    ducks: dict[str, DuckConversation] = {}

    for name, duck_config in config["ducks"].items():
        builder_path = duck_config["builder"]
        try:
            module_name, builder_name = builder_path.rsplit(":", 1)
        except ValueError as error:
            raise ValueError(
                f"Invalid duck builder '{builder_path}'; expected 'module:function'"
            ) from error

        try:
            module = import_module(module_name)
            builder: DuckBuilder = getattr(module, builder_name)
        except (ImportError, AttributeError) as error:
            raise ImportError(f"Could not load duck builder '{builder_path}'") from error

        if not callable(builder):
            raise TypeError(f"Duck builder is not callable: {builder_path}")

        duck = builder(
            name,
            duck_config["settings"],
            message_handler=message_handler,
            metrics_handler=metrics_handler,
            responses_api=responses_api,
            containers=containers,
            sql_session=sql_session,
            tool_configs=config.get("tools", {}),
        )
        if duck.name != name:
            raise ValueError(
                f"Duck builder for '{name}' returned a duck named '{duck.name}'"
            )
        ducks[name] = duck

    if not ducks:
        raise ValueError("No ducks configured")

    channel_ducks: dict[CHANNEL_ID, DuckConversation] = {}
    for channel in iter_channels(config):
        duck_name = channel.get("duck")
        if duck_name is None:
            continue
        if not isinstance(duck_name, str):
            raise TypeError(
                f"Channel {channel['channel_id']} must reference a named duck"
            )
        try:
            channel_ducks[channel["channel_id"]] = ducks[duck_name]
        except KeyError as error:
            raise KeyError(
                f"Duck '{duck_name}' referenced by channel "
                f"{channel['channel_id']} was not built"
            ) from error

    return channel_ducks


def create_workflow_manager(sql_session, workflows):
    return create_sql_manager(
        "rubber-duck",
        workflows.__getitem__,
        sql_session,
        serializer=workflow_serializer,
    )


def build_cache_cleaner(
        tool_caches: list[ToolCache],
        config: Config,
) -> CacheCleaner | None:
    unique_caches = list({id(cache): cache for cache in tool_caches}.values())
    if not unique_caches:
        return None

    settings = config.get("cache_cleanup_settings", {})
    return CacheCleaner(
        unique_caches,
        settings.get("cleanup_hour", 3),
        settings.get("cleanup_minute", 0),
    )


async def main(config: Config, log_path: Path | None):
    sql_session = create_sql_session(config["sql"])
    responses_api = ResponsesAPI(config["ai_completion_retry_protocol"])

    async with DiscordBot(bot_friend_ids=set(config.get("bot-friends", []))) as bot:
        filter_logs(bot.send_text, config["admin_settings"])
        metrics = SQLMetricsHandler(sql_session)
        feedback_manager = FeedbackManager({})

        with these(build_containers(config)) as containers:
            channel_ducks = build_ducks(
                config,
                message_handler=bot,
                metrics_handler=metrics,
                responses_api=responses_api,
                containers=containers,
                sql_session=sql_session,
            )
            ducks = {id(duck): duck for duck in channel_ducks.values()}.values()
            tool_caches = [
                cache
                for duck in ducks
                for cache in getattr(duck, "tool_caches", [])
            ]
            duck_commands = [
                command
                for duck in ducks
                for command in duck.commands
            ]

            orchestrator = DuckOrchestrator(
                SetupPrivateThread(bot.create_thread, bot.send_text),
                bot.send_text,
                bot.add_reaction,
                channel_ducks,
                feedback_manager.remember_conversation,
            )
            reporter = Reporter(
                metrics,
                config["servers"],
                config["reporter_settings"],
                True,
            )
            commands = create_commands(
                bot.send_text,
                metrics,
                reporter,
                log_path,
                tool_caches,
            )
            workflows = {
                "duck-orchestrator": orchestrator,
                "command": BotCommands(commands + duck_commands, bot.send_text),
            }
            channel_configs = {
                channel["channel_id"]: channel
                for channel in iter_channels(config)
                if channel["channel_id"] in channel_ducks
            }

            async with create_workflow_manager(sql_session, workflows) as workflow_manager:
                admin_channel = config["admin_settings"]["admin_channel_id"]
                app = RubberDuckApp(admin_channel, channel_configs, workflow_manager)
                bot.set_duck_app(app, admin_channel)

                tasks = [bot.start(os.environ["DISCORD_TOKEN"])]
                cache_cleaner = build_cache_cleaner(tool_caches, config)
                if cache_cleaner:
                    tasks.append(cache_cleaner.start())
                await asyncio.gather(*tasks)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        help="Path to config file (.json, .yaml, or s3://...)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--log-path", type=Path, help="Set the duck logger path")
    args = parser.parse_args()

    if args.debug:
        duck_logger.setLevel(logging.DEBUG)
    else:
        duck_logger.setLevel(logging.INFO)
        quest_logger.setLevel(logging.INFO)

    if args.log_path:
        add_file_handler(args.log_path)
    else:
        duck_logger.warning("No log path provided. Logging to console only.")
    add_console_handler()

    config_path = args.config or os.getenv("CONFIG_FILE_S3_PATH")
    config: Config = load_configuration(config_path)
    asyncio.run(main(config, args.log_path))
