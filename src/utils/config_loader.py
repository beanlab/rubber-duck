import io
import json
import os
from pathlib import Path
from typing import Any

import boto3
import yaml

from .config_types import Config
from .logger import duck_logger


def fetch_config_from_s3() -> Config | None:
    """Fetch configuration from S3 bucket"""
    try:
        # Initialize S3 client
        s3 = boto3.client('s3')

        # Add a section to your env file to allow for local and production environment
        environment = os.environ.get('ENVIRONMENT')
        if not environment or environment == 'LOCAL':
            duck_logger.info("Using LOCAL environment")
            return None
        else:
            duck_logger.info(f"Using PRODUCTION environment")

        # Get the S3 path from environment variables (CONFIG_FILE_S3_PATH should be set)
        s3_path = os.environ.get('CONFIG_FILE_S3_PATH')

        if not s3_path:
            duck_logger.warning("No S3 path configured")
            return None

        # Parse bucket name and key from the S3 path (s3://bucket-name/key)
        bucket_name, key = s3_path.replace('s3://', '').split('/', 1)
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
    Load configuration with fallback logic:
    1. Check command line argument
    2. Check environment variable CONFIG_FILE_S3_PATH
    3. Fall back to default config.json
    4. Handle S3 and local file loading with proper error handling
    """
    # Determine config path using match-case
    match (config_arg, os.environ.get('CONFIG_FILE_S3_PATH')):
        case (arg, _) if arg:
            config_path = arg
        case (_, env_path) if env_path:
            config_path = env_path
        case _:
            config_path = 'config.json'
    
    try:
        # Handle different path types using match-case
        match config_path:
            case path if path.startswith('s3://'):
                config = fetch_config_from_s3()
                if config is None:
                    raise RuntimeError(f"Failed to load configuration from S3: {path}")
                return config
            case path:
                config = load_local_config(Path(path))
                if config is None:
                    raise RuntimeError(f"Failed to load configuration from local file: {path}")
                return config
            
    except Exception as e:
        duck_logger.error(f"Configuration loading failed: {e}")
        raise RuntimeError(f"Failed to load configuration from {config_path}: {e}") 