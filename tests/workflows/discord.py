"""Application process lifecycle for Discord workflow tests."""

import asyncio
import atexit
import os
import signal
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

APPLICATION_ROOT = Path(__file__).resolve().parents[2]
DISCORD_STARTUP_TIMEOUT = 60
RUBBER_DUCK_ONLINE_TIMEOUT = 90
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


# Launch the application, observe Discord readiness, and release its owned process on exit.
@asynccontextmanager
async def run_discord_application(config_path: Path, admin_channel_id: int, actor_token: str):
    import discord

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
                    str(config_path),
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
