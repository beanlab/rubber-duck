import io
import json
import os
from copy import deepcopy
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


class IncludeLoader(yaml.SafeLoader):
    pass


def include_constructor(loader: IncludeLoader, node):
    """Load another YAML file relative to the current file."""
    base_path = Path(loader.name).parent
    include_path = base_path / loader.construct_scalar(node)

    if not include_path.exists():
        raise FileNotFoundError(f"Included config not found: {include_path}")

    with include_path.open() as f:
        return yaml.load(f, IncludeLoader)


IncludeLoader.add_constructor("!include", include_constructor)

def _include_single_with_overrides(loader: IncludeLoader, node):
    """
    Handles the YAML mapping case:
    key: !include_keys
      key: some-key
      from: path/to/file.yaml
      overrides: {...}
    """
    data = loader.construct_mapping(node, deep=True)
    key = data["key"]
    from_path = data["from"]
    overrides = data.get("overrides", {})

    included = _load_keys_from_file(from_path, [key])
    return {key: deep_merge(included[key], overrides)}


def _include_multiple_keys(loader: IncludeLoader, node):
    """
    Handles the scalar string form with multiple keys or wildcard:
    !include_keys key1, key2 from path/to/file.yaml
    !include_keys all from path/to/file.yaml
    Excludes keys that start with '_'
    """
    text = loader.construct_scalar(node)

    # parse "keys from path" pattern
    if " from " not in text:
        raise ValueError(f"Malformed !include_keys: {text}")
    keys_part, from_part = text.split(" from ", 1)
    from_path = from_part.strip()
    keys_part = keys_part.strip()

    # load all keys
    loaded = _load_keys_from_file(from_path, None)

    # determine keys to load
    if keys_part == "all":
        # exclude keys starting with "_"
        return {k: v for k, v in loaded.items() if not k.startswith("_")}
    else:
        keys = [k.strip() for k in keys_part.split(",")]
        return {k: loaded[k] for k in keys if k in loaded}

def _load_keys_from_file(file_path: str, keys: list[str] | None):
    """
    Loads specific keys (or all keys if keys=None) from a YAML file
    relative to the current loader file.
    """
    base_path = Path(file_path)
    if not base_path.is_absolute():
        base_path = Path.cwd() / file_path  # fallback

    if not base_path.exists():
        raise FileNotFoundError(f"Included config not found: {base_path}")

    with base_path.open() as f:
        content = yaml.load(f, IncludeLoader)
        if keys is None:
            return content  # return everything
        else:
            return {k: content[k] for k in keys if k in content}


def include_keys(loader: IncludeLoader, node):
    """
    Usage 1 (single, multiple, or 'all'):
      !include_keys standard-rubber-duck, stats-duck from configs/ducks-config.yaml

    Usage 2 (single key with overrides):
      standard-rubber-duck: !include_keys
        key: standard-rubber-duck
        from: configs/ducks-config.yaml
        overrides:
          settings:
            agent:
              engine: gpt-5-nano
    """
    if isinstance(node, yaml.ScalarNode):
        return _include_multiple_keys(loader, node)
    elif isinstance(node, yaml.MappingNode):
        return _include_single_with_overrides(loader, node)
    else:
        raise TypeError(f"!include_keys cannot handle node type: {type(node)}")


IncludeLoader.add_constructor("!include_keys", include_keys)


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
    stream = io.StringIO(content)
    loader = IncludeLoader(stream)
    if source_path:
        loader.name = str(source_path)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


def read_json(content: str) -> Config:
    """Parse JSON content into a dictionary"""
    return json.loads(content)


def load_config(file_type: str, content: str, source_path: Path | None = None) -> Config:
    """Load configuration based on file type, supporting !include in YAML"""
    match file_type:
        case '.json':
            return read_json(content)
        case '.yaml' | '.yml':
            return read_yaml(content, source_path=source_path)  # <-- MODIFIED
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
