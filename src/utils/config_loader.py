"""
Configuration loader supporting:

- Local and S3-backed config files
- JSON and YAML formats
- Recursive $include directives
- JSONPath selection within includes
- Deep-merge semantics for dict includes
"""
import json
import re
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, Set, Tuple

import boto3
import yaml
from jsonpath_ng import parse

from .config_types import Config
from .logger import duck_logger


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
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
    """
    Resolve a JSONPath expression against data.

    - If expr is empty, returns a deep copy of data.
    - If exactly one match is found, returns that value.
    - If multiple matches are found, returns a list of values.
    - Raises KeyError if no matches are found.
    """
    if not expr:
        return deepcopy(data)

    jsonpath_expr = parse(expr)
    matches = [match.value for match in jsonpath_expr.find(data)]

    if not matches:
        raise KeyError(f"JSONPath not found: {expr}")
    return deepcopy(matches[0] if len(matches) == 1 else matches)


# filesystem helper functions

def _read_s3_content(s3_uri: str) -> str:
    """Read content from S3 given an s3://bucket/key URI"""
    duck_logger.debug(f"Fetching config from S3: {s3_uri}")
    s3 = boto3.client("s3")
    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


def _read_local_content(path: str) -> str:
    return Path(path).read_text()


def _get_content(uri: str) -> str:
    if uri.startswith("s3://"):
        return _read_s3_content(uri)
    return _read_local_content(uri)


def _get_suffix(uri: str) -> str:
    return Path(uri).suffix  # works for both S3 and local paths


def _get_parent(uri: str) -> str:
    if uri.startswith("s3://"):
        return uri.rsplit("/", 1)[0]
    return str(Path(uri).parent)


def _join_uri(base: str, relative: str) -> str:
    """Resolve relative path against base for S3 and local paths"""
    if base.startswith("s3://"):
        prefix = "s3://"
        bucket_and_key = base[len(prefix):]
        bucket, key_prefix = bucket_and_key.split("/", 1)

        joined = PurePosixPath(key_prefix) / relative
        normalized = str(joined)

        return f"{prefix}{bucket}/{normalized}"
    return str((Path(base) / relative).resolve())


# include handling

INCLUDE_KEY_RE = re.compile(r"^\$include(?:_\d+)?$")


def _load_included_content(ref: str, base_uri: str, seen: Set[Tuple[str, str]]) -> Any:
    """
    Load and resolve an $include reference.

    Supports:
    - Optional JSONPath selector via `path@expr`
    - Cycle detection using the seen set
    - Recursive include resolution via _load_config
    """
    if "@" in ref:
        path_part, pointer = ref.rsplit("@", 1)
        pointer = pointer or ""
    else:
        path_part, pointer = ref, ""

    include_uri = _join_uri(base_uri, path_part)
    key = (include_uri, pointer)
    if key in seen:
        raise ValueError(f"Cyclic $include detected: {include_uri}@{pointer}")

    new_seen = seen.union({key})
    content = _load_config(include_uri, new_seen)
    return resolve_jsonpath(content, pointer)


def _resolve_include_block(
        data: dict[str, Any], include_keys: list[str], base_uri: str, seen: Set[Tuple[str, str]]
) -> Any:
    """
    Resolve a dict containing one or more $include keys.

    Semantics:
    - If all included values are dicts, they are deep-merged in sorted key order, then merged with sibling overrides.
    - If any included value is non-dict:
        * No sibling keys are allowed.
        * Exactly one include is allowed.
        * The included value replaces the entire node.
    """
    overrides = {k: v for k, v in data.items() if k not in include_keys}

    included_values = [
        _load_included_content(data[key], base_uri, seen)
        for key in include_keys
    ]

    # if all are dicts, merge
    if all(isinstance(v, dict) for v in included_values):
        merged: dict[str, Any] = {}
        for v in included_values:
            merged = deep_merge(merged, v)

        resolved_overrides = _resolve_includes(
            overrides, base_uri=base_uri, seen=seen
        )

        return deep_merge(merged, resolved_overrides)

    # non-dict includes cannot be merged with overrides
    if overrides:
        raise TypeError(
            "$include resolving to non-dict cannot have sibling keys"
        )

    # handle string includes
    if len(included_values) == 1:
        return included_values[0]

    raise TypeError(
        "Multiple non-dict $include entries cannot be merged"
    )


def _resolve_dict(data: dict[str, Any], base_uri: str, seen: Set[Tuple[str, str]]) -> Any:
    include_keys = sorted(k for k in data if INCLUDE_KEY_RE.match(k))

    if not include_keys:
        return {
            k: _resolve_includes(v, base_uri=base_uri, seen=seen)
            for k, v in data.items()
        }

    return _resolve_include_block(
        data, include_keys, base_uri=base_uri, seen=seen
    )


def _resolve_list(data: list[Any], base_uri: str, seen: Set[Tuple[str, str]]) -> list[Any]:
    return [_resolve_includes(item, base_uri=base_uri, seen=seen) for item in data]


def _resolve_includes(data: Any, base_uri: str, seen: Set[Tuple[str, str]]) -> Any:
    """
    Recursively resolve $include directives within arbitrary data.
    """
    if isinstance(data, dict):
        return _resolve_dict(data, base_uri=base_uri, seen=seen)

    if isinstance(data, list):
        return _resolve_list(data, base_uri=base_uri, seen=seen)

    return data


# config parsing

def _parse_config_from_content(content: str, suffix: str) -> Config:
    match suffix:
        case ".json":
            return json.loads(content)
        case ".yaml" | ".yml":
            return yaml.safe_load(content)
        case _:
            raise NotImplementedError(f"Unsupported config extension: {suffix}")


# main loaders

def _load_config(uri: str, seen: Set[Tuple[str, str]]) -> Config:
    """
    Load a configuration file from a URI and resolve all $include directives.

    Parameters:
    - uri: Local path or S3 URI
    - seen: Set of previously loaded (uri, pointer) tuples to prevent cycles

    Returns:
    - Fully resolved configuration dictionary
    """
    duck_logger.debug(f"Loading config: {uri}")
    content = _get_content(uri)
    suffix = _get_suffix(uri)
    base_uri = _get_parent(uri)

    raw_config = _parse_config_from_content(content, suffix)
    config = _resolve_includes(raw_config, base_uri=base_uri, seen=seen)
    return config


def load_configuration(config_uri: str) -> Config:
    """Load configuration from local file or S3 URI, resolving includes"""
    duck_logger.info(f"Loading config from: {config_uri}")
    final_config = _load_config(config_uri, set())
    duck_logger.debug(
        "Config loaded successfully:\n%s",
        yaml.dump(final_config, default_flow_style=False, sort_keys=False)
    )
    return final_config
