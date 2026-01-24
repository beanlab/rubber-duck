import copy
import yaml
from .logger import duck_logger
from .config_types import Config
from .config_local_types import LocalConfig, IncludeConfig, OverrideConfig


def _load_local_config(path: str) -> LocalConfig:
    with open(path, "r") as f:
        contents = yaml.safe_load(f)
        duck_logger.debug("Loaded local config from YAML")
        return LocalConfig(**contents)


def _empty_config() -> Config:
    duck_logger.debug("Creating empty config shell")
    return {
        "sql": {},
        "containers": [],
        "tools": [],
        "ducks": [],
        "agents_as_tools": [],
        "servers": {},
        "admin_settings": {},
        "dataset_folder_locations": [],
        "ai_completion_retry_protocol": {},
        "feedback_notifier_settings": {},
        "reporter_settings": {},
        "sender_email": "",
    }


def _include_top_level_sections(base: Config, target: Config, sections: list[str]):
    for key in sections:
        if key not in base:
            raise KeyError(f"Unknown config section: {key}")
        target[key] = copy.deepcopy(base[key])


def _include_named_items(
        base_items: list[dict],
        target_items: list[dict],
        names: list[str],
        name_key: str = "name",
):
    lookup = {item[name_key]: item for item in base_items}
    duck_logger.debug(f"Including named items: {names}")
    for name in names:
        if name not in lookup:
            raise KeyError(f"{name_key} '{name}' not found in base config")
        target_items.append(copy.deepcopy(lookup[name]))


def _include_servers(base: Config, target: Config, server_ids: list[str]):
    for server_id in server_ids:
        if server_id not in base.get("servers", {}):
            raise KeyError(f"Server ID {server_id} not found in base config")
        target["servers"][server_id] = copy.deepcopy(base["servers"][server_id])


def _apply_includes(base_config: Config, include: IncludeConfig) -> Config:
    duck_logger.debug("Applying includes...")
    include_all = include.get("include_all", False)
    result: Config = copy.deepcopy(base_config) if include_all else _empty_config()

    if include.get("include_these"):
        _include_top_level_sections(base_config, result, include["include_these"])

    if include.get("containers"):
        _include_named_items(
            base_items=base_config.get("containers", []),
            target_items=result["containers"],
            names=[c["name"] for c in include["containers"]],
        )

    if include.get("ducks"):
        _include_named_items(
            base_items=base_config.get("ducks", []),
            target_items=result["ducks"],
            names=[d["name"] for d in include["ducks"]],
        )

    if include.get("tools"):
        _include_named_items(
            base_items=base_config.get("tools", []),
            target_items=result["tools"],
            names=[t["name"] for t in include["tools"]],
        )

    if include.get("agents_as_tools"):
        _include_named_items(
            base_items=base_config.get("agents_as_tools", []),
            target_items=result["agents_as_tools"],
            names=[a["tool_name"] for a in include["agents_as_tools"]],
            name_key="tool_name",
        )

    if include.get("servers"):
        _include_servers(base_config, result, include["servers"])

    duck_logger.debug("Includes applied successfully")
    return result


def deep_merge_dict(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        elif isinstance(result.get(key), list) and isinstance(value, list):
            merged_list = []
            for i, v in enumerate(value):
                if i < len(result[key]) and isinstance(result[key][i], dict) and isinstance(v, dict):
                    merged_list.append(deep_merge_dict(result[key][i], v))
                else:
                    merged_list.append(copy.deepcopy(v))
            result[key] = merged_list
        else:
            result[key] = copy.deepcopy(value)
    return result


def merge_named_list(base_items: list[dict], override_items: list[dict], name_key: str = "name") -> list[dict]:
    base_lookup = {item[name_key]: item for item in base_items}
    result: list[dict] = []
    seen = set()

    for override in override_items:
        name = override[name_key]
        if name in base_lookup:
            merged = deep_merge_dict(base_lookup[name], override)
            result.append(merged)
        else:
            result.append(copy.deepcopy(override))
        seen.add(name)

    for name, item in base_lookup.items():
        if name not in seen:
            result.append(copy.deepcopy(item))

    return result


def merge_servers(base_servers: dict, override_servers: dict) -> dict:
    result = copy.deepcopy(base_servers)
    for server_id, override_server in override_servers.items():
        if server_id not in result:
            result[server_id] = copy.deepcopy(override_server)
            continue

        base_server = result[server_id]
        merged_server = deep_merge_dict(base_server, override_server)

        if "channels" in override_server:
            base_channels = {c["channel_id"]: c for c in base_server.get("channels", [])}
            merged_channels = []
            seen_channels = set()

            for ch in override_server["channels"]:
                cid = ch["channel_id"]
                if cid in base_channels:
                    merged = deep_merge_dict(base_channels[cid], ch)
                    merged_channels.append(merged)
                else:
                    merged_channels.append(copy.deepcopy(ch))
                seen_channels.add(cid)

            for cid, ch in base_channels.items():
                if cid not in seen_channels:
                    merged_channels.append(copy.deepcopy(ch))

            merged_server["channels"] = merged_channels

        result[server_id] = merged_server

    return result


def _apply_overrides(config: Config, override: OverrideConfig) -> Config:
    duck_logger.debug("Applying overrides...")
    result = copy.deepcopy(config)

    def to_dict(obj):
        if isinstance(obj, dict):
            return {k: to_dict(v) for k, v in obj.items()}
        elif hasattr(obj, "__dict__"):
            return {k: to_dict(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [to_dict(x) for x in obj]
        else:
            return obj

    override_dict = to_dict(override)

    for key, value in override_dict.items():
        if isinstance(value, dict):
            result[key] = deep_merge_dict(result.get(key, {}), value)
        elif isinstance(value, list) and key in ["ducks", "containers", "tools", "agents_as_tools"]:
            result[key] = merge_named_list(result.get(key, []), value,
                                           name_key="tool_name" if key=="agents_as_tools" else "name")
        else:
            result[key] = value

    duck_logger.debug("Overrides applied successfully")
    return result


def override_configuration(base_config: Config, local_config_path: str) -> Config:
    duck_logger.debug("Loading local config...")
    local: LocalConfig = _load_local_config(local_config_path)

    # Convert TypedDicts to regular dicts for easier merging
    local_dict = copy.deepcopy(local)

    include_config = local_dict.get("include", {})
    final_config = _apply_includes(base_config, include_config)

    override_config = local_dict.get("override", {})
    # Ensure we convert the TypedDict override to a normal dict before merging
    override_dict = copy.deepcopy(override_config)
    final_config = _apply_overrides(final_config, override_dict)

    duck_logger.debug("Final config ready")
    return final_config
