import argparse
import asyncio
import logging
import os
import threading
import traceback
from pathlib import Path
from typing import Iterable, Any

from openai import OpenAI
from quest import these
from quest.extras.sql import SqlBlobStorage
from quest.utils import quest_logger

from src.utils.protocols import ToolCache, CacheKeyBuilder
from src.armory.tool_cache import InMemoryToolCache, SemanticCacheKeyBuilder, SqlToolCache
from src.workflows.registration import Registration
from src.workflows.assignment_feedback_workflow import AssignmentFeedbackWorkflow
from src.utils.python_exec_container import build_containers, PythonExecContainer
from src.armory.python_tools import PythonTools
from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.bot.discord_bot import DiscordBot
from src.commands.bot_commands import BotCommands
from src.commands.command import create_commands
from src.conversation.conversation import AgentLedConversation, UserLedConversation
from src.conversation.threads import SetupPrivateThread
from src.duck_orchestrator import DuckOrchestrator, DuckConversation
from src.gen_ai.build import build_agent
from src.gen_ai.gen_ai import AIClient
from src.metrics.feedback import HaveTAGradingConversation, ConversationReviewSettings
from src.metrics.feedback_manager import FeedbackManager, CHANNEL_ID
from src.metrics.reporter import Reporter
from src.rubber_duck_app import RubberDuckApp
from src.storage.sql_connection import create_sql_session
from src.storage.sql_metrics import SQLMetricsHandler
from src.storage.sql_quest import create_sql_manager
from src.utils.config_loader import load_configuration
from src.utils.config_types import CacheCleanupSettings, CacheSettings, Config, RegistrationSettings, DUCK_NAME, \
    DuckConfig, ToolConfig
from src.utils.cache_cleaner import CacheCleaner
from src.utils.feedback_notifier import FeedbackNotifier
from src.utils.logger import duck_logger, filter_logs, add_console_handler, add_file_handler
from src.utils.persistent_queue import PersistentQueue
from src.utils.send_email import EmailSender
from src.workflows.registration_workflow import RegistrationWorkflow

_log_forwarding_lock = threading.Lock()
_log_forwarding_installed = False


def setup_workflow_manager(
        config: Config,
        duck_orchestrator,
        sql_session,
        metrics_handler,
        send_message,
        log_dir: Path,
        tool_caches: list[ToolCache],
):
    reporter = Reporter(metrics_handler, config['servers'], config['reporter_settings'], True)

    commands = create_commands(send_message, metrics_handler, reporter, log_dir, tool_caches)
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
        name: str, bot: DiscordBot, config: Config, settings: RegistrationSettings, armory
):
    registration_bot = armory.get_specific_tool(settings['registration_bot'])

    email_confirmation = EmailSender(config['sender_email'])

    registration = Registration(
        bot.send_message,
        bot.get_channel,
        bot.fetch_guild,
        email_confirmation,
        settings
    )
    armory.scrub_tools(registration)
    registration_workflow = RegistrationWorkflow(name, registration, registration_bot)

    return registration_workflow


def _iterate_duck_configs(config: Config) -> Iterable[tuple[DUCK_NAME, DuckConfig]]:
    # Global ducks
    for name, duck_cfg in config["ducks"].items():
        yield name, duck_cfg

    # Inline channel ducks
    for server in config["servers"].values():
        for channel in server["channels"].values():
            duck = channel.get("duck")

            # Reference to global duck
            if isinstance(duck, DUCK_NAME):
                continue

            # Inline definition(s)
            if isinstance(duck, dict):
                for name, duck_cfg in duck.items():
                    if isinstance(duck_cfg, dict) and "duck_type" in duck_cfg:
                        yield name, duck_cfg


def build_ducks(
        config: Config,
        bot: DiscordBot,
        metrics_handler,
        feedback_manager,
        ai_client,
        armory,
        talk_tool
) -> dict[DUCK_NAME, DuckConversation]:
    ducks = {}

    for name, duck_config in _iterate_duck_configs(config):
        duck_type = duck_config['duck_type']
        settings = duck_config['settings']

        if duck_type == 'agent_led_conversation':
            starting_agent = build_agent(settings["agent"])
            ducks[name] = AgentLedConversation(name, starting_agent, ai_client)

        elif duck_type == 'user_led_conversation':
            starting_agent = build_agent(settings["agent"])
            ducks[name] = UserLedConversation(name, starting_agent, ai_client, talk_tool, settings['introduction'])

        elif duck_type == 'conversation_review':
            ducks[name] = build_conversation_review_duck(
                name, settings, bot, metrics_handler.record_feedback, feedback_manager
            )

        elif duck_type == 'registration':
            if not (hasattr(bot, 'get_channel') and hasattr(bot, 'fetch_guild')):
                duck_logger.warning(
                    f"Skipping registration duck '{name}': "
                    f"bot adapter does not support get_channel/fetch_guild"
                )
                continue
            ducks[name] = build_registration_duck(name, bot, config, settings, armory)


        elif duck_type == 'assignment_feedback':
            single_rubric_item_grader = build_agent(settings["single_rubric_item_grader"])
            project_scanner_agent = build_agent(settings["project_scanner_agent"])
            ducks[name] = AssignmentFeedbackWorkflow(
                name,
                bot.send_message,
                settings,
                single_rubric_item_grader,
                project_scanner_agent,
                ai_client,
                bot.read_url
            )

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
        ai_client,
        armory,
        talk_tool
) -> dict[CHANNEL_ID, DuckConversation]:
    """
    Return a dictionary of channel ID to DuckConversation
    """
    all_ducks = build_ducks(config, bot, metrics_handler, feedback_manager, ai_client, armory, talk_tool)

    channel_ducks: dict[CHANNEL_ID, DuckConversation] = {}

    for server_config in config["servers"].values():
        for channel_name, channel_config in server_config["channels"].items():
            channel_id = channel_config["channel_id"]

            duck_cfg = channel_config.get("duck")
            if duck_cfg is None:
                continue

            if isinstance(duck_cfg, str):
                duck_name = duck_cfg

            elif isinstance(duck_cfg, dict):
                duck_name, duck_cfg = next(iter(duck_cfg.items()))

            else:
                raise ValueError(
                    f"Invalid duck config for channel {channel_id}: {duck_cfg}"
                )

            try:
                channel_ducks[channel_id] = all_ducks[duck_name]
            except KeyError:
                raise KeyError(
                    f"Duck '{duck_name}' referenced in channel {channel_id} was not built"
                )
    return channel_ducks


def _build_feedback_queues(config: Config, sql_session):
    queue_blob_storage = SqlBlobStorage('conversation-queues', sql_session)

    convo_review_ducks = (
        duck
        for _, duck in _iterate_duck_configs(config)
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


def _build_cache_key_builder(cache_settings: CacheSettings, tool_name: str) -> CacheKeyBuilder:
    prompt = cache_settings.get("prompt")
    if not prompt:
        raise ValueError(
            f"Missing cache prompt for container_exec tool '{tool_name}'. "
            f"Set tools.{tool_name}.cache.prompt."
        )

    return SemanticCacheKeyBuilder(
        client=OpenAI(),
        prompt=Path(prompt).read_text(),
        model=cache_settings.get("engine", "gpt-5-nano"),
        reasoning_effort=cache_settings.get("reasoning", "minimal"),
    )


def _build_tool_cache(cache_settings: CacheSettings, sql_session) -> ToolCache:
    backend = cache_settings.get("backend", "memory")

    if backend == "memory":
        return InMemoryToolCache()

    if backend == "database":
        return SqlToolCache(sql_session)

    raise NotImplementedError(f"Unsupported cache backend: {backend}")


def _get_tool_cache_settings(tool_config: ToolConfig) -> CacheSettings | None:
    if "cache" not in tool_config:
        return None
    return dict(tool_config.get("cache", {}))


def build_armory(
        config: Config,
        send_message,
        containers: dict[str, PythonExecContainer],
        sql_session
) -> tuple[Armory, TalkTool, list[ToolCache]]:
    armory = Armory(send_message)
    tool_caches: list[ToolCache] = []

    # setup tools
    config_tools = config.get("tools", [])
    for tool_name, tool_config in config_tools.items():
        if tool_config['type'] == 'container_exec':
            container_name = tool_config['container']
            cache_settings = _get_tool_cache_settings(tool_config)
            tool_cache = None
            cache_key_builder = None
            if cache_settings is not None:
                tool_cache = _build_tool_cache(cache_settings, sql_session)
                setattr(tool_cache, "_cache_source", tool_name)
                tool_caches.append(tool_cache)
                cache_key_builder = _build_cache_key_builder(cache_settings, tool_name)
            python_tools = PythonTools(
                containers[container_name],
                send_message,
                tool_cache,
                cache_key_builder
            )
            amended_description = (
                    tool_config.get('description', python_tools.run_code.__doc__)
                    + '\n'
                    + containers[container_name].get_resource_metadata()
            )
            armory.add_tool(python_tools.run_code, name=tool_name, description=amended_description)
        else:
            duck_logger.warning(f"Unsupported tool type: {tool_config['type']}")

    talk_tool = TalkTool(send_message)
    armory.scrub_tools(talk_tool)

    return armory, talk_tool, tool_caches


def _setup_cache_cleaner(
        tool_caches: list[ToolCache],
        cache_cleanup_settings: CacheCleanupSettings | None = None
) -> CacheCleaner:
    unique_tool_caches: list[ToolCache] = []
    seen_cache_ids: set[int] = set()
    for tool_cache in tool_caches:
        cache_id = id(tool_cache)
        if cache_id not in seen_cache_ids:
            seen_cache_ids.add(cache_id)
            unique_tool_caches.append(tool_cache)
    cc = None
    if unique_tool_caches:
        cache_cleanup_settings = cache_cleanup_settings or {}
        cleanup_hour = cache_cleanup_settings.get("cleanup_hour", 3)
        cleanup_minute = cache_cleanup_settings.get("cleanup_minute", 0)
        cc = CacheCleaner(
            unique_tool_caches,
            cleanup_hour,
            cleanup_minute
        )
    return cc



def add_agent_tools_to_armory(config: Config, armory: Armory, ai_client: AIClient):
    for name, settings in config.get("agents_as_tools", {}).items():
        agent = build_agent(settings["agent"])
        tool = ai_client.build_agent_tool(
            agent, name, settings["doc_string"]
        )
        armory.add_tool(tool)


def _configure_log_forwarding_once(send_message, admin_settings) -> None:
    global _log_forwarding_installed
    with _log_forwarding_lock:
        if _log_forwarding_installed:
            return
        filter_logs(send_message, admin_settings)
        _log_forwarding_installed = True


async def run_discord_mode(config: Config, log_dir: Path | None):
    config = _build_platform_config(config, "discord")
    sql_session = create_sql_session(config['sql'])

    async with DiscordBot() as bot:
        setup_thread = SetupPrivateThread(
            bot.create_thread,
            bot.send_message
        )

        _configure_log_forwarding_once(bot.send_message, config['admin_settings'])

        with _build_feedback_queues(config, sql_session) as persistent_queues:
            feedback_manager = FeedbackManager(persistent_queues)
            metrics_handler = SQLMetricsHandler(sql_session)

            with these(build_containers(config)) as containers:
                armory, talk_tool, tool_caches = build_armory(
                    config,
                    bot.send_message,
                    containers,
                    sql_session,
                )
                ai_client = AIClient(armory, bot.typing, metrics_handler.record_message, metrics_handler.record_usage)
                add_agent_tools_to_armory(config, armory, ai_client)

                ducks = _setup_ducks(config, bot, metrics_handler, feedback_manager, ai_client, armory, talk_tool)

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
                    for channel_config in server_config['channels'].values()
                }

                async with setup_workflow_manager(
                        config,
                        duck_orchestrator,
                        sql_session,
                        metrics_handler,
                        bot.send_message,
                        log_dir,
                        tool_caches,
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

                    if tool_caches:
                        cleaner = _setup_cache_cleaner(
                            tool_caches,
                            config.get("cache_cleanup_settings", {})
                        )
                        tasks.append(cleaner.start())

                    await asyncio.gather(*tasks)


def _build_teams_aiohttp_app(teams_bot, adapter):
    from aiohttp import web
    from aiohttp.web import Request, Response, json_response
    from botbuilder.schema import Activity

    async def messages(req: Request) -> Response:
        if 'application/json' not in req.headers.get('Content-Type', ''):
            return Response(status=415, text='Unsupported media type')

        body = await req.json()
        activity = Activity().deserialize(body)
        auth_header = req.headers.get('Authorization', '')

        try:
            invoke_response = await adapter.process_activity(activity, auth_header, teams_bot.on_turn)
        except Exception:
            masked_auth = (auth_header[:20] + '...') if len(auth_header) > 20 else auth_header
            duck_logger.exception(
                'Error processing Teams activity\n'
                '  auth_header (first 20 chars): %s\n'
                '  raw activity body: %s',
                masked_auth,
                body,
            )
            return Response(status=500)

        if invoke_response:
            return json_response(data=invoke_response.body, status=invoke_response.status)

        return Response(status=201)

    async def health(_req: Request) -> Response:
        return json_response({'status': 'ok'})

    app = web.Application()
    app.router.add_post('/api/messages', messages)
    app.router.add_get('/health', health)
    return app


async def run_teams_mode(config: Config, log_dir: Path | None, port: int):
    config = _build_platform_config(config, "teams")
    from aiohttp import web
    from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
    from src.bot.teams_bot import TeamsBot

    app_id = os.environ['MICROSOFT_APP_ID']
    app_password = os.environ['MICROSOFT_APP_PASSWORD']
    app_tenant_id = os.environ.get('MICROSOFT_APP_TENANT_ID', '')
    duck_logger.info(
        'Teams credentials loaded: app_id=%s password_present=%s tenant_id=%s',
        app_id, bool(app_password), app_tenant_id,
    )

    settings = BotFrameworkAdapterSettings(
        app_id=app_id,
        app_password=app_password,
        channel_auth_tenant=app_tenant_id,
    )
    adapter = BotFrameworkAdapter(settings)

    async def on_error(context: TurnContext, error: Exception) -> None:
        duck_logger.exception(f'[on_turn_error] unhandled error: {error}')
        traceback.print_exc()
        await context.send_activity('The bot encountered an error. Please try again.')

    adapter.on_turn_error = on_error

    teams_bot = TeamsBot(adapter, app_id)
    sql_session = create_sql_session(config['sql'])
    setup_thread = SetupPrivateThread(teams_bot.create_thread, teams_bot.send_message)
    _configure_log_forwarding_once(teams_bot.send_message, config['admin_settings'])

    with _build_feedback_queues(config, sql_session) as persistent_queues:
        feedback_manager = FeedbackManager(persistent_queues)
        metrics_handler = SQLMetricsHandler(sql_session)

        with these(build_containers(config)) as containers:
            armory, talk_tool, tool_caches = build_armory(
                config, teams_bot.send_message, containers, sql_session
            )
            ai_client = AIClient(
                armory, teams_bot.typing,
                metrics_handler.record_message, metrics_handler.record_usage,
            )
            add_agent_tools_to_armory(config, armory, ai_client)

            ducks = _setup_ducks(
                config, teams_bot, metrics_handler, feedback_manager, ai_client, armory, talk_tool,
            )

            duck_orchestrator = DuckOrchestrator(
                setup_thread,
                teams_bot.send_message,
                teams_bot.add_reaction,
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
                teams_bot.send_message, log_dir, tool_caches,
            ) as workflow_manager:
                admin_channel_id = config['admin_settings']['admin_channel_id']
                rubber_duck = RubberDuckApp(admin_channel_id, channel_configs, workflow_manager)
                teams_bot.set_duck_app(rubber_duck, admin_channel_id)

                aiohttp_app = _build_teams_aiohttp_app(teams_bot, adapter)
                runner = web.AppRunner(aiohttp_app)
                await runner.setup()
                site = web.TCPSite(runner, '0.0.0.0', port)
                await site.start()

                duck_logger.info(f'Teams bot listening on http://0.0.0.0:{port}/api/messages')

                tasks = []
                if 'feedback_notifier_settings' in config:
                    notifier = FeedbackNotifier(
                        feedback_manager,
                        teams_bot.send_message,
                        config['servers'].values(),
                        config['feedback_notifier_settings'],
                    )
                    tasks.append(notifier.start())
                if tool_caches:
                    cleaner = _setup_cache_cleaner(tool_caches, config.get("cache", {}))
                    tasks.append(cleaner.start())

                try:
                    if tasks:
                        await asyncio.gather(*tasks)
                    else:
                        await asyncio.Event().wait()
                finally:
                    await runner.cleanup()


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Start the rubber-duck bot runtime')
    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file (.json or .yaml, or s3://...). Falls back to CONFIG_FILE_S3_PATH.'
    )
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--log-path', type=Path, help='Set the log path for the duck logger')
    parser.add_argument(
        '--port', type=int,
        default=int(os.environ.get('PORT', 3000)),
        help='HTTP listen port for Teams mode (default: 3000)',
    )
    return parser


def _configure_logging(debug: bool, log_path: Path | None) -> None:
    if debug:
        duck_logger.setLevel(logging.DEBUG)
        quest_logger.setLevel(logging.DEBUG)
    else:
        duck_logger.setLevel(logging.INFO)
        quest_logger.setLevel(logging.INFO)

    if log_path:
        add_file_handler(log_path)
    else:
        duck_logger.warning('No log path provided. Logging to console only.')

    add_console_handler()


def _load_runtime_config(config_path: str | None) -> Config:
    resolved_path = config_path or os.getenv('CONFIG_FILE_S3_PATH')
    if resolved_path is None:
        raise ValueError('Missing --config and CONFIG_FILE_S3_PATH is not set')
    return load_configuration(resolved_path)


def _is_server_config(server_config: Any) -> bool:
    return isinstance(server_config, dict) and "server_id" in server_config and "channels" in server_config


def _extract_platform_servers(config: Config, platform: str) -> dict[str, Any]:
    servers = config.get("servers", {})

    if not isinstance(servers, dict):
        duck_logger.warning("Invalid config: 'servers' must be a dictionary. Ignoring.")
        return {}

    platform_servers = servers.get(platform)
    if platform_servers is None:
        return {}
    if not isinstance(platform_servers, dict):
        duck_logger.warning("Invalid config: servers.%s must be a dictionary. Ignoring.", platform)
        return {}
    if platform_servers and not all(_is_server_config(v) for v in platform_servers.values()):
        duck_logger.warning(
            "Invalid config: servers.%s must map server names to server configs. Ignoring.",
            platform,
        )
        return {}
    return platform_servers


def _build_platform_config(config: Config, platform: str) -> Config:
    platform_servers = _extract_platform_servers(config, platform)
    if not platform_servers:
        raise ValueError(f"No {platform} servers configured")

    platform_config: Config = dict(config)
    platform_config["servers"] = platform_servers
    return platform_config


def _get_configured_platforms(config: Config) -> list[str]:
    servers = config.get("servers", {})
    if not isinstance(servers, dict):
        duck_logger.warning("Invalid config: 'servers' must be a dictionary. Ignoring.")
        return []

    platforms: list[str] = []

    for key in servers.keys():
        if key == "discord":
            if _extract_platform_servers(config, "discord"):
                platforms.append("discord")
        elif key == "teams":
            if _extract_platform_servers(config, "teams"):
                platforms.append("teams")
        else:
            duck_logger.warning(
                "Unknown server platform key '%s' in config.servers. Ignoring.",
                key,
            )

    return platforms


async def run_from_args(args: argparse.Namespace) -> None:
    config = _load_runtime_config(args.config)
    platforms = _get_configured_platforms(config)

    if not platforms:
        duck_logger.warning(
            "No configured platform servers found under config.servers.discord or config.servers.teams."
        )
        return

    if platforms == ["discord"]:
        duck_logger.info("Starting runtime in discord mode (from config)")
        await run_discord_mode(config, args.log_path)
        return

    if platforms == ["teams"]:
        duck_logger.info("Starting runtime in teams mode (from config)")
        await run_teams_mode(config, args.log_path, args.port)
        return

    duck_logger.info("Starting runtime in both mode (from config)")
    await asyncio.gather(
        run_discord_mode(config, args.log_path),
        run_teams_mode(config, args.log_path, args.port),
    )


async def main() -> None:
    parser = build_cli_parser()
    args = parser.parse_args()
    _configure_logging(args.debug, args.log_path)
    try:
        await run_from_args(args)
    except Exception:
        duck_logger.exception('ERROR in MAIN')


if __name__ == '__main__':
    asyncio.run(main())
