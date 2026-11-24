"""Fixtures and scenario selection for live Discord conversation tests."""

import asyncio
import os
from pathlib import Path

import pytest

from evaluation.results import UsageCollector
from src.gen_ai.gen_ai import Agent
from src.utils.config_loader import load_configuration
from tests.workflows.discord import DISCORD_STARTUP_TIMEOUT, run_discord_application
from .driver import TesterBot
from .usage import conversation_cost_report

DEFAULT_RUBBER_DUCK_CONFIG = Path(__file__).with_name("config.yaml")
TESTERBOT_DEBOUNCE_SECONDS = 4.0
TESTERBOT_TOKEN_ENV = "ACTOR_TOKEN"
TESTERBOT_MODEL = "gpt-5.6-luna"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is required to run the tester bot e2e test.")
    return value


def get_rubber_duck_config_path(pytestconfig) -> Path:
    path = Path(pytestconfig.getoption("--config") or DEFAULT_RUBBER_DUCK_CONFIG)
    if not path.exists():
        pytest.skip(f"--config must point to an existing config file: {path}")
    return path


@pytest.fixture(scope="session")
def rubber_duck_config(pytestconfig):
    return load_configuration(str(get_rubber_duck_config_path(pytestconfig)))


@pytest.fixture(scope="session")
def duck_channel_id(rubber_duck_config):
    def find_channel_id(duck_name: str) -> int:
        matches = {
            channel["channel_id"]
            for server in rubber_duck_config["servers"].values()
            for channel in server["channels"].values()
            if channel.get("duck") == duck_name
            or isinstance(channel.get("duck"), dict)
            and duck_name in channel["duck"]
        }

        if len(matches) != 1:
            raise ValueError(
                f"Expected one channel configured for duck {duck_name}, "
                f"found {len(matches)}."
            )

        return int(next(iter(matches)))

    return find_channel_id


# Acquire the real application process through the shared workflow test driver.
@pytest.fixture(scope="session")
async def rubber_duck_run(pytestconfig, rubber_duck_config):
    require_env("DISCORD_TOKEN")
    require_env("OPENAI_API_KEY")
    actor_token = require_env(TESTERBOT_TOKEN_ENV)
    async with run_discord_application(
        get_rubber_duck_config_path(pytestconfig),
        int(rubber_duck_config["admin_settings"]["admin_channel_id"]),
        actor_token,
    ) as process:
        yield process


@pytest.fixture
def report_conversation_cost(rubber_duck_config):
    return lambda testerbot: conversation_cost_report(testerbot, rubber_duck_config)


@pytest.fixture(scope="session")
async def testerbot(rubber_duck_run, rubber_duck_config):
    token = require_env(TESTERBOT_TOKEN_ENV)
    admin_channel_id = int(rubber_duck_config["admin_settings"]["admin_channel_id"])
    usage_collector = UsageCollector()

    bot = TesterBot(
        admin_channel_id=admin_channel_id,
        debounce_seconds=TESTERBOT_DEBOUNCE_SECONDS,
        agent=Agent(
            name="TestBot",
            prompt="",
            model=TESTERBOT_MODEL,
            tools=[],
            reasoning="low",
        ),
        record_usage=usage_collector.record_usage,
    )
    bot.usage_collector = usage_collector

    async with bot:
        bot_task = asyncio.create_task(bot.start(token))
        try:
            await asyncio.wait_for(
                bot.wait_until_ready(),
                timeout=DISCORD_STARTUP_TIMEOUT,
            )
        except TimeoutError:
            pytest.fail("Timed out waiting for testerbot to connect to Discord.")

        try:
            yield bot
        finally:
            await bot.close()
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
