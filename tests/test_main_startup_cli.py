import asyncio
from types import SimpleNamespace

import pytest

from src import main as entrypoint


def test_build_cli_parser_supports_platform_modes():
    parser = entrypoint.build_cli_parser()

    args = parser.parse_args(
        [
            "--platform",
            "discord",
            "--config",
            "discord.yaml",
        ]
    )
    assert args.platform == "discord"
    assert args.config == "discord.yaml"

    args = parser.parse_args(
        [
            "--platform",
            "teams",
            "--config",
            "teams.yaml",
            "--port",
            "3333",
        ]
    )
    assert args.platform == "teams"
    assert args.config == "teams.yaml"
    assert args.port == 3333


def test_build_cli_parser_requires_separate_configs_for_both_mode():
    parser = entrypoint.build_cli_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--platform",
                "both",
                "--config",
                "shared.yaml",
            ]
        )

    args = parser.parse_args(
        [
            "--platform",
            "both",
            "--discord-config",
            "discord.yaml",
            "--teams-config",
            "teams.yaml",
        ]
    )
    assert args.platform == "both"
    assert args.discord_config == "discord.yaml"
    assert args.teams_config == "teams.yaml"


def test_run_from_args_dispatches_discord_mode(monkeypatch):
    calls = {"discord": 0, "teams": 0, "configs": []}

    async def fake_discord(config, log_path):
        calls["discord"] += 1
        assert config["name"] == "discord"
        assert log_path is None

    async def fake_teams(_config, _log_path, _port):
        calls["teams"] += 1

    def fake_load_configuration(path):
        calls["configs"].append(path)
        return {"name": "discord"}

    monkeypatch.setattr(entrypoint, "run_discord_mode", fake_discord)
    monkeypatch.setattr(entrypoint, "run_teams_mode", fake_teams)
    monkeypatch.setattr(entrypoint, "load_configuration", fake_load_configuration)

    args = SimpleNamespace(
        platform="discord",
        config="discord.yaml",
        discord_config=None,
        teams_config=None,
        port=3000,
        log_path=None,
    )

    asyncio.run(entrypoint.run_from_args(args))

    assert calls["discord"] == 1
    assert calls["teams"] == 0
    assert calls["configs"] == ["discord.yaml"]


def test_run_from_args_dispatches_both_mode_with_separate_configs(monkeypatch):
    calls = {"discord": 0, "teams": 0, "configs": []}

    async def fake_discord(config, _log_path):
        calls["discord"] += 1
        assert config["name"] == "discord"

    async def fake_teams(config, _log_path, port):
        calls["teams"] += 1
        assert config["name"] == "teams"
        assert port == 4000

    def fake_load_configuration(path):
        calls["configs"].append(path)
        return {"name": "discord" if "discord" in path else "teams"}

    monkeypatch.setattr(entrypoint, "run_discord_mode", fake_discord)
    monkeypatch.setattr(entrypoint, "run_teams_mode", fake_teams)
    monkeypatch.setattr(entrypoint, "load_configuration", fake_load_configuration)

    args = SimpleNamespace(
        platform="both",
        config=None,
        discord_config="discord.yaml",
        teams_config="teams.yaml",
        port=4000,
        log_path=None,
    )

    asyncio.run(entrypoint.run_from_args(args))

    assert calls["discord"] == 1
    assert calls["teams"] == 1
    assert calls["configs"] == ["discord.yaml", "teams.yaml"]
