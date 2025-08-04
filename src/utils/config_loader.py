import io
import json
import os
from pathlib import Path
from typing import Any

import boto3
import yaml

from .config_types import Config
from .logger import duck_logger


def fetch_config_from_s3(config_path) -> Config | None:
    """Fetch configuration from S3 bucket"""
    try:
        # Initialize S3 client
        s3 = boto3.client('s3')

        # Use the config_path parameter instead of environment variable
        if not config_path:
            raise ValueError("S3 config path is required but not provided")
        
        duck_logger.info(f"Fetching config from S3 path: {config_path}")

        # Parse bucket name and key from the S3 path (s3://bucket-name/key)
        bucket_name, key = config_path.replace('s3://', '').split('/', 1)
        duck_logger.info(f"Fetching config from bucket: {bucket_name}")
        duck_logger.info(f"Config key: {key}")

        # Download file from S3
        response = s3.get_object(Bucket=bucket_name, Key=key)

        # Read the content of the file and parse it
        content = response['Body'].read().decode('utf-8')
        config = load_config('.' + key.split('.')[-1], content)
        duck_logger.info("Successfully loaded config from S3")
        return config

    except Exception as e:
        duck_logger.error(f"Failed to fetch config from S3: {e}")
        return None


def read_yaml(content: str) -> Config:
    """Parse YAML content into a dictionary"""
    return yaml.safe_load(io.StringIO(content))


def read_json(content: str) -> Config:
    """Parse JSON content into a dictionary"""
    return json.loads(content)


def load_config(file_type: str, content: str) -> Config:
    """Load configuration based on file type"""
    match file_type:
        case '.json':
            return read_json(content)
        case '.yaml' | '.yml':
            return read_yaml(content)
        case _:
            raise NotImplementedError(f'Unsupported config extension: {file_type}')


def load_local_config(config_path: Path) -> Config:
    """Load configuration from a local file"""
    return load_config(config_path.suffix, config_path.read_text())


def load_configuration(config_arg: str | None = None) -> Config:
    """
    1. Check command line argument
    2. Check environment variable CONFIG_FILE_S3_PATH
    3. Handle S3 and local file loading with proper error handling
    """
    if config_arg:
        config_path = config_arg
    else:
        env_path = os.environ.get('CONFIG_FILE_S3_PATH') or 'config.json'
        if env_path:
            config_path = env_path
        else:
            config_path = 'config.json'

    try:
        if config_path.startswith('s3://'):
            config = fetch_config_from_s3(config_path)
            if config is None:
                raise RuntimeError(f"Failed to load configuration from S3: {config_path}")
        else:
            config = load_local_config(Path(config_path))
            if config is None:
                raise RuntimeError(f"Failed to load configuration from local file: {config_path}")
        return config

    except Exception:
        raise
