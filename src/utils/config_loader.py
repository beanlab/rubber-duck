import json
import os
from copy import deepcopy
from jsonpath_ng import parse
from pathlib import Path
from typing import Any

import boto3
import yaml

from .config_types import Config
from .logger import duck_logger


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict:
    """Recursively merge two dicts, with override taking precedence."""

    result = deepcopy(base)
    for key, value in override.items():
        if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def resolve_jsonpath(data: Any, expr: str) -> Any:
    if not expr:
        return deepcopy(data)

    jsonpath_expr = parse(expr)
    matches = [match.value for match in jsonpath_expr.find(data)]

    if not matches:
        raise KeyError(f"JSONPath not found: {expr}")

    # single match returns the value,
    # multiple matches return a list
    if len(matches) == 1:
        return deepcopy(matches[0])

    return deepcopy(matches)


def load_include(ref: str, base_path: Path, seen: set[tuple[Path, str]]) -> Any:
    if ":" in ref:
        path_part, pointer = ref.split(":", 1)
        pointer = pointer or ""
    else:
        path_part, pointer = ref, ""

    include_path = (base_path / path_part).resolve()

    key = (include_path, pointer)
    if key in seen:
        raise ValueError(f"Cyclic $include detected: {include_path}:{pointer}")

    new_seen = seen.union({key})

    if not include_path.exists():
        raise FileNotFoundError(f"Included config not found: {include_path}")

    content = include_path.read_text()
    data = load_config(include_path.suffix, content, source_path=include_path)

    resolved_data = resolve_includes(data, base_path=include_path.parent, seen=new_seen)

    return resolve_jsonpath(resolved_data, pointer)


def resolve_includes(data: Any, *, base_path: Path, seen: set[tuple[Path, str]] | None = None) -> Any:
    if seen is None:
        seen = set()
    if isinstance(data, dict):
        if "$include" in data:
            include_ref = data["$include"]
            duck_logger.debug(f"including: {include_ref}")
            overrides = {k: v for k, v in data.items() if k != "$include"}

            included = load_include(include_ref, base_path, seen)

            resolved_overrides = resolve_includes(
                overrides, base_path=base_path, seen=seen
            )

            return deep_merge(included, resolved_overrides)

        return {
            k: resolve_includes(v, base_path=base_path, seen=seen)
            for k, v in data.items()
        }

    # allow includes within lists
    if isinstance(data, list):
        return [
            resolve_includes(item, base_path=base_path, seen=seen)
            for item in data
        ]

    return data


def fetch_config_from_s3(config_path) -> Config:
    """Fetch configuration from S3 bucket"""
    s3 = boto3.client('s3')

    if not config_path:
        duck_logger.error("No S3 config path provided.")
        raise

    duck_logger.info(f"Fetching config from S3 path: {config_path}")

    bucket_name, key = config_path.replace('s3://', '').split('/', 1)
    duck_logger.info(f"Fetching config from bucket: {bucket_name}")
    duck_logger.info(f"Config key: {key}")

    response = s3.get_object(Bucket=bucket_name, Key=key)

    content = response['Body'].read().decode('utf-8')

    ext = '.' + key.split('.')[-1]
    config = load_config(ext, content, source_path=Path(key))
    duck_logger.info("Successfully loaded config from S3")
    return config


def read_yaml(content: str, source_path: Path | None = None) -> Config:
    """Parse YAML content into a dictionary, with !include support"""
    data = yaml.safe_load(content)
    if source_path:
        return resolve_includes(data, base_path=source_path.parent)
    return data


def read_json(content: str, source_path: Path | None = None) -> Config:
    """Parse JSON content into a dictionary"""
    data = json.loads(content)
    if source_path:
        return resolve_includes(data, base_path=source_path.parent)
    return data


def load_config(file_type: str, content: str, source_path: Path | None = None) -> Config:
    """Load configuration based on file type, supporting !include in YAML"""
    match file_type:
        case '.json':
            return read_json(content, source_path=source_path)
        case '.yaml' | '.yml':
            return read_yaml(content, source_path=source_path)
        case _:
            raise NotImplementedError(f'Unsupported config extension: {file_type}')


def load_local_config(config_path: Path) -> Config:
    """Load configuration from a local file"""
    return load_config(config_path.suffix, config_path.read_text(), source_path=config_path)


def load_configuration(base_cfg: str | None, merge_cfg: str | None = None) -> Config:
    """
    Load the base configuration, optionally overlay a local config.
    Handles S3 and local file loading.
    """

    # TODO: do we still use s3 or json configs?
    config_path = base_cfg or os.environ.get('CONFIG_FILE_S3_PATH') or 'config.json'
    duck_logger.info(f"Loading config from: {config_path}")

    # Load base config
    if config_path.startswith('s3://'):
        base_config = fetch_config_from_s3(config_path)
    else:
        base_config = load_local_config(Path(config_path))

    # Overlay local config if provided
    if merge_cfg:
        duck_logger.info(f"Applying overlay config: {merge_cfg}")

        if merge_cfg.startswith('s3://'):
            overlay_config = fetch_config_from_s3(merge_cfg)
        else:
            overlay_config = load_local_config(Path(merge_cfg))

        final_config = deep_merge(base_config, overlay_config)
    else:
        final_config = base_config

    return final_config
