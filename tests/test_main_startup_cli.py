import asyncio
from types import SimpleNamespace

from src import main as entrypoint


def test_build_cli_parser_supports_platform_modes():
    parser = entrypoint.build_cli_parser()

    args = parser.parse_args(
        [
            "--config",
            "discord.yaml",
        ]
    )
    assert args.config == "discord.yaml"
    assert args.port == 3000


def test_run_from_args_dispatches_discord_mode(monkeypatch):
    calls = {"discord": 0, "teams": 0, "configs": []}

    async def fake_discord(config, log_path):
        calls["discord"] += 1
        assert "servers" in config
        assert log_path is None

    async def fake_teams(_config, _log_path, _port):
        calls["teams"] += 1

    def fake_load_configuration(path):
        calls["configs"].append(path)
        return {"servers": {"discord": {"BeanLab": {"server_id": 1, "channels": {}}}}}

    monkeypatch.setattr(entrypoint, "run_discord_mode", fake_discord)
    monkeypatch.setattr(entrypoint, "run_teams_mode", fake_teams)
    monkeypatch.setattr(entrypoint, "load_configuration", fake_load_configuration)

    args = SimpleNamespace(
        config="discord.yaml",
        port=3000,
        log_path=None,
    )

    asyncio.run(entrypoint.run_from_args(args))

    assert calls["discord"] == 1
    assert calls["teams"] == 0
    assert calls["configs"] == ["discord.yaml"]


def test_run_from_args_dispatches_both_modes_from_single_config(monkeypatch):
    calls = {"discord": 0, "teams": 0, "configs": []}

    async def fake_discord(config, _log_path):
        calls["discord"] += 1
        assert "servers" in config

    async def fake_teams(config, _log_path, port):
        calls["teams"] += 1
        assert "servers" in config
        assert port == 4000

    def fake_load_configuration(path):
        calls["configs"].append(path)
        assert path == "combined.yaml"
        return {
            "servers": {
                "discord": {"BeanLab": {"server_id": 1, "channels": {}}},
                "teams": {"MyTeams": {"server_id": "x", "channels": {}}},
            }
        }

    monkeypatch.setattr(entrypoint, "run_discord_mode", fake_discord)
    monkeypatch.setattr(entrypoint, "run_teams_mode", fake_teams)
    monkeypatch.setattr(entrypoint, "load_configuration", fake_load_configuration)

    args = SimpleNamespace(
        config="combined.yaml",
        port=4000,
        log_path=None,
    )

    asyncio.run(entrypoint.run_from_args(args))

    assert calls["discord"] == 1
    assert calls["teams"] == 1
    assert calls["configs"] == ["combined.yaml"]


def test_run_from_args_ignores_unknown_platform_keys(monkeypatch):
    calls = {"discord": 0, "teams": 0}

    async def fake_discord(_config, _log_path):
        calls["discord"] += 1

    async def fake_teams(_config, _log_path, _port):
        calls["teams"] += 1

    def fake_load_configuration(_path):
        return {"servers": {"BeanLab": {"server_id": 1, "channels": {}}}}

    monkeypatch.setattr(entrypoint, "run_discord_mode", fake_discord)
    monkeypatch.setattr(entrypoint, "run_teams_mode", fake_teams)
    monkeypatch.setattr(entrypoint, "load_configuration", fake_load_configuration)

    args = SimpleNamespace(
        config="legacy.yaml",
        port=3000,
        log_path=None,
    )

    asyncio.run(entrypoint.run_from_args(args))

    assert calls["discord"] == 0
    assert calls["teams"] == 0
