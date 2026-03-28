"""Entry point for the Teams adapter.

Usage:
    python run_teams.py --config path/to/config.yaml [--debug] [--log-path /logs] [--port 3000]

Required environment variables:
    MicrosoftAppId        Azure AD application (client) ID
    MicrosoftAppPassword  Azure AD client secret

Optional environment variables:
    MicrosoftAppTenantId  Azure AD tenant ID (required for SingleTenant bots)
    PORT                  HTTP listen port (default: 3000; overridden by --port)
    CONFIG_FILE_S3_PATH   Config URI fallback when --config is not supplied

A .env file in the working directory is loaded automatically if present.
"""

import argparse
import asyncio
import logging
import os
import traceback
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
from quest import these
from quest.utils import quest_logger

from src.bot.teams_bot import TeamsBot
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
    load_dotenv(override=True)
except ImportError:
    pass


def _build_aiohttp_app(bot: TeamsBot, adapter: BotFrameworkAdapter) -> web.Application:
    async def messages(req: Request) -> Response:
        if 'application/json' not in req.headers.get('Content-Type', ''):
            return Response(status=415, text='Unsupported media type')

        body = await req.json()
        activity = Activity().deserialize(body)
        auth_header = req.headers.get('Authorization', '')

        try:
            invoke_response = await adapter.process_activity(activity, auth_header, bot.on_turn)
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


async def _main_teams(config: Config, log_dir: Path | None, port: int) -> None:
    app_id = os.environ['MICROSOFT_APP_ID']
    app_password = os.environ['MICROSOFT_APP_PASSWORD']
    app_tenant_id = os.environ.get('MICROSOFT_APP_TENANT_ID', '')
    app_type = os.environ.get("MICROSOFT_APP_TYPE", "SingleTenant")
    duck_logger.info(
        'Teams credentials loaded: app_id=%s password_len=%d password_prefix=%s tenant_id=%s app_type=%s',
        app_id, len(app_password), app_password[:4], app_tenant_id, app_type,
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

    # Note: _setup_ducks passes bot to build_ducks which is typed as DiscordBot,
    # but works at runtime via duck typing for all duck types except 'registration'
    # (which calls bot.get_channel / bot.fetch_guild, not present on TeamsBot).
    bot = TeamsBot(adapter, app_id)

    sql_session = create_sql_session(config['sql'])

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

                aiohttp_app = _build_aiohttp_app(bot, adapter)
                runner = web.AppRunner(aiohttp_app)
                await runner.setup()
                site = web.TCPSite(runner, '0.0.0.0', port)
                await site.start()

                duck_logger.info(f'Teams bot listening on http://0.0.0.0:{port}/api/messages')

                tasks = []
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

                try:
                    if tasks:
                        await asyncio.gather(*tasks)
                    else:
                        await asyncio.Event().wait()  # run until interrupted
                finally:
                    await runner.cleanup()


async def main(config: Config, log_dir: Path | None, port: int) -> None:
    try:
        await _main_teams(config, log_dir, port)
    except Exception as ex:
        duck_logger.exception('ERROR in MAIN')
        print(ex)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start the Teams rubber-duck bot')
    parser.add_argument(
        '--config', type=str,
        help='Path to config file (.json or .yaml, or s3://...)',
    )
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--log-path', type=Path, help='Set the log path for the duck logger')
    parser.add_argument(
        '--port', type=int,
        default=int(os.environ.get('PORT', 3000)),
        help='HTTP listen port (default: 3000)',
    )

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

    asyncio.run(main(config, args.log_path, args.port))
