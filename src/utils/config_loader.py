import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import boto3
import yaml
from jsonpath_ng import parse

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


def _load_included_content(ref: str, base_path: Path, seen: set[tuple[Path, str]]) -> Any:
    if "@" in ref:
        path_part, pointer = ref.split("@")[-2:]
        pointer = pointer or ""
    else:
        path_part, pointer = ref, ""

    include_path = (base_path / path_part).resolve()

    key = (include_path, pointer)
    if key in seen:
        raise ValueError(f"Cyclic $include detected: {include_path}:{pointer}")

    new_seen = seen.union({key})

    content = _load_config(include_path, new_seen)

    return resolve_jsonpath(content, pointer)


INCLUDE_KEY_RE = re.compile(r"^\$include(?:_\d+)?$")


def _resolve_includes(data: Any, *, base_path: Path, seen: set[tuple[Path, str]]) -> Any:
    if isinstance(data, dict):
        include_keys = sorted(
            k for k in data if INCLUDE_KEY_RE.match(k)
        )

        if include_keys:

            overrides = {
                k: v for k, v in data.items() if k not in include_keys
            }

            merged = {}
            for key in include_keys:
                include_ref = data[key]
                included = _load_included_content(include_ref, base_path, seen)
                merged = deep_merge(merged, included)

            resolved_overrides = _resolve_includes(
                overrides, base_path=base_path, seen=seen
            )

            return deep_merge(merged, resolved_overrides)

        return {
            k: _resolve_includes(v, base_path=base_path, seen=seen)
            for k, v in data.items()
        }

    # allow includes within lists
    if isinstance(data, list):
        return [
            _resolve_includes(item, base_path=base_path, seen=seen)
            for item in data
        ]

    return data


def _read_s3_content(config_path: str) -> str:
    """Fetch configuration from S3 bucket"""
    duck_logger.debug(f"Fetching config from S3 path: {config_path}")

    s3 = boto3.client('s3')
    bucket_name, key = config_path.replace('s3://', '').split('/', 1)

    duck_logger.debug(f"Fetching config from bucket: {bucket_name}")
    duck_logger.debug(f"Config key: {key}")

    response = s3.get_object(Bucket=bucket_name, Key=key)
    content = response['Body'].read().decode('utf-8')

    return content


def _parse_config_from_content(
        content: str,
        source_path_suffix: str,
) -> Config:
    """Load configuration from raw content based on file suffix."""
    match source_path_suffix:
        case '.json':
            return json.loads(content)
        case '.yaml' | '.yml':
            return yaml.safe_load(content)
        case _:
            raise NotImplementedError(f"Unsupported config extension: {source_path_suffix}")


def _load_config(source_path: Path, seen: set) -> Config:
    """Load configuration based on file type, supporting !include in YAML"""
    duck_logger.debug(f'Loading {source_path}')

    if str(source_path).startswith('s3://'):
        def get_content(config_path: Path) -> str:
            return _read_s3_content(str(config_path))

    else:
        def get_content(config_path: Path) -> str:
            return config_path.read_text()

    content = get_content(source_path)

    raw_config = _parse_config_from_content(content, source_path.suffix)

    config = _resolve_includes(
        raw_config,
        base_path=source_path.parent,
        seen=seen
    )

    return config


def load_configuration(config_path: str) -> Config:
    """
    Load the base configuration.
    Handles S3 and local file loading.
    """
    duck_logger.info(f"Loading config from: {config_path}")
    final_config = _load_config(Path(config_path), set())
    duck_logger.debug(
        "Config loaded successfully. Full config: \n%s",
        yaml.dump(final_config, default_flow_style=False, sort_keys=False)
    )
    return final_config
