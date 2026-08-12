import asyncio
import atexit
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.gen_ai.gen_ai import Agent
from src.utils.config_loader import load_configuration
from src.testing.tester_bot_scaffold.assessments import (
    PostConversationAssessment,
    assess_conversation,
)
from src.testing.tester_bot_scaffold.testerbot import TesterBot


APPLICATION_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RUBBER_DUCK_CONFIG = (
    APPLICATION_ROOT / "local-testing-configs/local_christian_config.yaml"
)
DISCORD_STARTUP_TIMEOUT = 60
RUBBER_DUCK_ONLINE_TIMEOUT = 90
TESTERBOT_DEBOUNCE_SECONDS = 4.0


def pytest_addoption(parser):
    parser.addoption(
        "--config",
        action="store",
        help="Path to the rubber duck application config for the e2e test.",
    )


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
        matches = [
            channel["channel_id"]
            for server in rubber_duck_config["servers"].values()
            for channel in server["channels"].values()
            if channel.get("duck") == duck_name
            or isinstance(channel.get("duck"), dict)
            and duck_name in channel["duck"]
        ]

        if len(matches) != 1:
            raise ValueError(
                f"Expected one channel configured for duck {duck_name}, "
                f"found {len(matches)}."
            )

        return int(matches[0])

    return find_channel_id


_DISCORD_PROCESSES: list[subprocess.Popen] = []
_CLEANUP_REGISTERED = False
_PREVIOUS_SIGNAL_HANDLERS = {}


def terminate_discord_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError:
            process.terminate()
    else:
        process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
            except OSError:
                process.kill()
        else:
            process.kill()
        process.wait()


def cleanup_discord_processes() -> None:
    for process in list(_DISCORD_PROCESSES):
        terminate_discord_process(process)


def handle_exit_signal(signum, frame) -> None:
    cleanup_discord_processes()
    previous_handler = _PREVIOUS_SIGNAL_HANDLERS.get(signum)
    if callable(previous_handler):
        previous_handler(signum, frame)
        return
    if previous_handler == signal.SIG_IGN:
        return
    if signum == signal.SIGINT:
        raise KeyboardInterrupt
    raise SystemExit(128 + signum)


def register_discord_process_cleanup(process: subprocess.Popen) -> None:
    global _CLEANUP_REGISTERED

    _DISCORD_PROCESSES.append(process)
    if _CLEANUP_REGISTERED:
        return

    atexit.register(cleanup_discord_processes)
    for signum in (signal.SIGINT, signal.SIGTERM):
        _PREVIOUS_SIGNAL_HANDLERS[signum] = signal.getsignal(signum)
        signal.signal(signum, handle_exit_signal)
    _CLEANUP_REGISTERED = True


def unregister_discord_process_cleanup(process: subprocess.Popen) -> None:
    if process in _DISCORD_PROCESSES:
        _DISCORD_PROCESSES.remove(process)


@pytest.fixture(scope="session")
async def rubber_duck_run(pytestconfig, rubber_duck_config):
    import discord

    require_env("DISCORD_TOKEN")
    require_env("OPENAI_API_KEY")
    actor_token = require_env("ACTOR_TOKEN")
    rubber_duck_config_path = get_rubber_duck_config_path(pytestconfig)
    admin_channel_id = int(rubber_duck_config["admin_settings"]["admin_channel_id"])

    intents = discord.Intents.default()
    intents.message_content = True
    listener = discord.Client(intents=intents)

    process = None
    async with listener:
        listener_task = asyncio.create_task(listener.start(actor_token))
        try:
            try:
                await asyncio.wait_for(
                    listener.wait_until_ready(),
                    timeout=DISCORD_STARTUP_TIMEOUT,
                )
            except TimeoutError:
                pytest.fail(
                    "Timed out waiting for the rubber duck readiness listener "
                    "to connect to Discord."
                )

            started_at = datetime.now(timezone.utc)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "src.main",
                    "--config",
                    str(rubber_duck_config_path),
                    "--debug",
                ],
                cwd=APPLICATION_ROOT,
                start_new_session=os.name == "posix",
            )
            register_discord_process_cleanup(process)

            try:
                admin_channel = await listener.fetch_channel(admin_channel_id)
                deadline = (
                    asyncio.get_running_loop().time()
                    + RUBBER_DUCK_ONLINE_TIMEOUT
                )
                while True:
                    async for _message in admin_channel.history(
                        limit=20,
                        after=started_at,
                    ):
                        break
                    else:
                        if process.poll() is not None:
                            pytest.fail(
                                "Rubber duck subprocess exited before sending "
                                "an admin-channel online message. "
                                f"Return code: {process.returncode}."
                            )
                        if asyncio.get_running_loop().time() >= deadline:
                            raise TimeoutError
                        await asyncio.sleep(1)
                        continue
                    break
            except TimeoutError:
                pytest.fail(
                    "Timed out waiting for a rubber duck online message in "
                    f"admin channel {admin_channel_id}."
                )
        finally:
            await listener.close()
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

    try:
        yield process
    finally:
        if process is not None:
            terminate_discord_process(process)
            unregister_discord_process_cleanup(process)


@pytest.fixture(scope="session")
async def testerbot(rubber_duck_run, rubber_duck_config):
    token = require_env("ACTOR_TOKEN")
    admin_channel_id = int(rubber_duck_config["admin_settings"]["admin_channel_id"])

    bot = TesterBot(
        admin_channel_id=admin_channel_id,
        debounce_seconds=TESTERBOT_DEBOUNCE_SECONDS,
        agent=Agent(
            name="TestBot",
            prompt="",
            model="gpt-5.4-nano",
            tools=[],
            reasoning="low",
        ),
    )

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


async def create_assessment(
    testerbot: TesterBot,
    *,
    channel_id: int,
    thread_opener: str,
    base_prompt: str,
    progress_assessor: Agent | None = None,
    conversation_timeout: float,
    post_conversation_assessor: Agent,
) -> PostConversationAssessment:
    conversation = await asyncio.wait_for(
        testerbot.run_conversation(
            channel_id=channel_id,
            thread_opener=thread_opener,
            base_prompt=base_prompt,
            progress_assessor=progress_assessor,
        ),
        timeout=conversation_timeout,
    )

    if testerbot.last_context is None:
        raise RuntimeError("TesterBot did not create a DuckContext for the conversation.")

    return await assess_conversation(
        ai_client=testerbot.ai_client,
        ctx=testerbot.last_context,
        history=conversation,
        assessor=post_conversation_assessor,
    )
