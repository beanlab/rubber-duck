import json
import boto3
from pathlib import Path
from .logger import duck_logger


def _is_s3(path: str) -> bool:
    return path.startswith("s3://")


def _is_metadata(name: str) -> bool:
    return name.endswith(".meta.json")


_s3_client = boto3.client("s3")


def _format_description(metadata: dict) -> str:
    lines = []

    name = metadata.get("name")
    if name:
        lines.append(f"Dataset name: {name}")

    columns = metadata.get("columns", [])
    if columns:
        lines.append("Columns:")
        for col in columns:
            col_name = col.get("name", "unknown")
            dtype = col.get("dtype", "")
            desc = col.get("description", "")

            line = f"- {col_name}"
            if dtype:
                line += f", ({dtype})"
            if desc:
                line += f": {desc}"

            lines.append(line)

    return "\n".join(lines)


# ==================== #
# ======== s3 ======== #
# ==================== #


def _split_s3_path(path: str) -> tuple[str, str]:
    path = path.replace("s3://", "", 1)
    bucket, key = path.split("/", 1)
    return bucket, key


def _get_s3_desc(path: str) -> str:
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


def _get_s3_bytes(path: str) -> bytes:
    duck_logger.debug(f"Reading S3 dataset bytes: {path}")

    bucket, key = _split_s3_path(path)
    obj = _s3_client.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()

    duck_logger.debug(f"Read {len(data)} bytes from S3 dataset: {path}")
    return data


def _get_s3_folder_info(path: str) -> list[tuple[str, bytes]]:
    duck_logger.debug(f"Loading S3 folder datasets: {path}")

    bucket, prefix = _split_s3_path(path)
    if not prefix.endswith("/"):
        prefix += "/"

    paginator = _s3_client.get_paginator("list_objects_v2")

    results: list[tuple[str, bytes]] = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            # skip folders
            if key.endswith("/"):
                continue

            filename = key.split("/")[-1]
            if _is_metadata(filename):
                continue

            dataset_path = f"s3://{bucket}/{key}"
            duck_logger.debug(f"Processing S3 dataset file: {dataset_path}")

            desc = _get_s3_desc(dataset_path)
            data = _get_s3_bytes(dataset_path)
            results.append((desc, data))

    return results


# ===================== #
# ======= local ======= #
# ===================== #


def _get_local_desc(path: str) -> str:
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


def _get_local_bytes(path: str) -> bytes:
    duck_logger.debug(f"Reading local dataset bytes: {path}")

    data = Path(path).read_bytes()
    duck_logger.debug(f"Read {len(data)} bytes from local dataset: {path}")
    return data


def _get_local_folder_info(path: str) -> list[tuple[str, bytes]]:
    duck_logger.debug(f"Loading local folder datasets: {path}")

    folder = Path(path)
    if not folder.is_dir():
        raise ValueError(f"Local path is not a directory: {path}")

    results: list[tuple[str, bytes]] = []

    for file_path in folder.iterdir():
        if not file_path.is_file():
            continue
        if _is_metadata(file_path.name):
            continue

        duck_logger.debug(f"Processing local dataset file: {file_path}")
        desc = _get_local_desc(str(file_path))
        data = _get_local_bytes(str(file_path))
        results.append((desc, data))

    return results


# ======================== #
# ======== public ======== #
# ======================== #


def determine_mount_case(remote_path: str, target_path: str) -> str:
    """
    Returns the mount case for the given remote path and target path and returns the filename
        - folder: folder
        - file: folder
        - file: folder/file
    :returns: case, filename
    """
    # check if both are directories
    if remote_path.endswith("/") and target_path.endswith("/"):
        return "folder: folder"
    # check if file: folder
    elif not remote_path.endswith("/") and target_path.endswith("/"):
        return "file: folder"
    # check if file: file
    elif not remote_path.endswith("/") and not target_path.endswith("/"):
        return "file: file"
    else:
        duck_logger.error(f"Invalid mount case - remote path: {remote_path}, target path: {target_path}")
        return ""


def get_folder_info(folder_path: str) -> list[tuple[str, bytes]]:
    """Returns a list of all descriptions and bytes of every dataset in the folder"""
    # a folder will have dataset-metadata pairs in the format <dataset_name>.csv and <dataset_name>.meta.json
    if _is_s3(folder_path):
        return _get_s3_folder_info(folder_path)
    else:
        return _get_local_folder_info(folder_path)


def get_dataset_info(file_path: str) -> tuple[str, bytes]:
    """
    Returns the description and bytes of a dataset
    :param file_path: automatically parses s3 and local file paths
    :return:
    """
    duck_logger.debug(f"Preparing dataset for mount: {file_path}")

    if _is_s3(file_path):
        duck_logger.debug(f"Detected S3 dataset path: {file_path}")
        description = _get_s3_desc(file_path)
        data = _get_s3_bytes(file_path)
    else:
        duck_logger.debug(f"Detected local dataset path: {file_path}")
        description = _get_local_desc(file_path)
        data = _get_local_bytes(file_path)

    return description, data
