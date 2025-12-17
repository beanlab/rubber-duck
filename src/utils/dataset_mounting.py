import json
from pathlib import Path
import boto3
from .logger import duck_logger


def is_s3(path: str) -> bool:
    return path.startswith("s3://")


_s3_client = boto3.client("s3")


def _split_s3_path(path: str) -> tuple[str, str]:
    path = path.replace("s3://", "", 1)
    bucket, key = path.split("/", 1)
    return bucket, key


def _format_description(metadata: dict) -> str:
    lines = []

    name = metadata.get("name")
    if name:
        lines.append(f"Dataset: {name}")
        lines.append("")

    columns = metadata.get("columns", [])
    if columns:
        lines.append("Columns:")
        for col in columns:
            col_name = col.get("name", "unknown")
            dtype = col.get("dtype", "")
            desc = col.get("description", "")

            line = f"- {col_name}"
            if dtype:
                line += f" ({dtype})"
            if desc:
                line += f": {desc}"

            lines.append(line)

    return "\n".join(lines)


def get_local_desc(path: str) -> str:
    duck_logger.debug(f"Loading local metadata for dataset: {path}")

    file_path = Path(path)
    meta_path = file_path.with_suffix(".meta.json")

    if not meta_path.exists():
        duck_logger.warn(f"No local metadata found, using fallback description: {path}")
        return f"Dataset file: {file_path.name}"

    try:
        metadata = json.loads(meta_path.read_text())
        duck_logger.debug(f"Local metadata loaded successfully: {meta_path}")
        return _format_description(metadata)

    except Exception:
        duck_logger.error(f"Failed to parse local metadata JSON: {meta_path}", exc_info=True)
        return f"Dataset file: {file_path.name}"


def get_local_bytes(path: str) -> bytes:
    duck_logger.debug(f"Reading local dataset bytes: {path}")

    data = Path(path).read_bytes()
    duck_logger.debug(f"Read {len(data)} bytes from local dataset: {path}")
    return data


def get_s3_desc(path: str) -> str:
    duck_logger.debug(f"Loading S3 metadata for dataset: {path}")

    bucket, key = _split_s3_path(path)
    meta_key = key.rsplit(".", 1)[0] + ".meta.json"

    try:
        obj = _s3_client.get_object(Bucket=bucket, Key=meta_key)
        metadata = json.loads(obj["Body"].read().decode("utf-8"))

        duck_logger.debug(f"S3 metadata loaded successfully: s3://{bucket}/{meta_key}")
        return _format_description(metadata)

    except _s3_client.exceptions.NoSuchKey:
        duck_logger.warn(f"No S3 metadata found, using fallback description: {path}")
        return f"Dataset file: {key.split('/')[-1]}"

    except Exception:
        duck_logger.error(
            f"Failed to load or parse S3 metadata JSON: s3://{bucket}/{meta_key}",
            exc_info=True,
        )
        return f"Dataset file: {key.split('/')[-1]}"


def get_s3_bytes(path: str) -> bytes:
    duck_logger.debug(f"Reading S3 dataset bytes: {path}")

    bucket, key = _split_s3_path(path)
    obj = _s3_client.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()

    duck_logger.debug(f"Read {len(data)} bytes from S3 dataset: {path}")
    return data


def get_dataset_info(path: str) -> tuple[str, bytes]:
    """
    Returns the description and bytes of a dataset
    :param path: automatically parses s3 and local file paths
    :return:
    """
    duck_logger.debug(f"Preparing dataset for mount: {path}")

    if is_s3(path):
        duck_logger.debug(f"Detected S3 dataset path: {path}")
        description = get_s3_desc(path)
        data = get_s3_bytes(path)
    else:
        duck_logger.debug(f"Detected local dataset path: {path}")
        description = get_local_desc(path)
        data = get_local_bytes(path)

    duck_logger.debug(f"Dataset ready for mount: {path}")
    return description, data
