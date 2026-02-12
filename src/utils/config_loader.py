import json
import re
from copy import deepcopy
from jsonpath_ng import parse
from pathlib import Path
from typing import Any, Callable

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
    if "@" in ref:
        path_part, pointer = ref.split("@", 1)
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
    included_config = load_config_from_content(content, include_path)

    # resolve nested includes
    resolved_data = resolve_includes(included_config, base_path=include_path.parent, seen=new_seen)

    return resolve_jsonpath(resolved_data, pointer)


INCLUDE_KEY_RE = re.compile(r"^\$include(?:_\d+)?$")


def resolve_includes(data: Any, *, base_path: Path, seen: set[tuple[Path, str]] | None = None) -> Any:
    if seen is None:
        seen = set()
    if isinstance(data, dict):
        include_keys = sorted(
            k for k in data if INCLUDE_KEY_RE.match(k)
        )

        if include_keys:
            duck_logger.debug(f"including: {include_keys}")

            overrides = {
                k: v for k, v in data.items() if k not in include_keys
            }

            merged = {}
            for key in include_keys:
                include_ref = data[key]
                included = load_include(include_ref, base_path, seen)
                merged = deep_merge(merged, included)

            resolved_overrides = resolve_includes(
                overrides, base_path=base_path, seen=seen
            )

            return deep_merge(merged, resolved_overrides)

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


def fetch_config_from_s3(config_path: str) -> Config:
    """Fetch configuration from S3 bucket"""
    if not config_path:
        duck_logger.error("No S3 config path provided.")
        raise ValueError("config_path is required")

    duck_logger.debug(f"Fetching config from S3 path: {config_path}")

    s3 = boto3.client('s3')
    bucket_name, key = config_path.replace('s3://', '').split('/', 1)

    duck_logger.debug(f"Fetching config from bucket: {bucket_name}")
    duck_logger.debug(f"Config key: {key}")

    response = s3.get_object(Bucket=bucket_name, Key=key)
    content = response['Body'].read().decode('utf-8')

    config = load_config_from_content(
        content=content,
        source_path=Path(key),
    )

    duck_logger.debug("Successfully loaded config from S3")
    return config


def read_contents(content: str, loader: Callable, source_path: Path) -> Config:
    """Reads contents using a specific loader method"""
    data = loader(content)
    resolved = resolve_includes(data, base_path=source_path.parent)
    return resolved


def load_config_from_content(
        content: str,
        source_path: Path,
) -> Config:
    """Load configuration from raw content based on file suffix."""
    match source_path.suffix:
        case '.json':
            return read_contents(content, json.loads, source_path)
        case '.yaml' | '.yml':
            return read_contents(content, yaml.safe_load, source_path)
        case _:
            raise NotImplementedError(f"Unsupported config extension: {source_path.suffix}")


def load_config(source_path: str) -> Config:
    """Load configuration based on file type, supporting !include in YAML"""
    if source_path.startswith('s3://'):
        return fetch_config_from_s3(source_path)

    path = Path(source_path)
    content = path.read_text()

    return load_config_from_content(content, path)


def load_configuration(config_path: str) -> Config:
    """
    Load the base configuration.
    Handles S3 and local file loading.
    """
    duck_logger.info(f"Loading config from: {config_path}")
    final_config = load_config(config_path)
    duck_logger.debug(
        "Config loaded successfully. Full config: \n%s",
        yaml.dump(final_config, default_flow_style=False, sort_keys=False)
    )
    return final_config
