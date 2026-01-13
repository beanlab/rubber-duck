import json
from pathlib import Path
from typing import Iterable
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .logger import duck_logger


@dataclass(frozen=True)
class DatasetInfo:
    filename: str
    description: str
    data: bytes

    # Optional future metadata
    size: Optional[int] = None
    source_path: Optional[str] = None


# ======================= #
# ======== config ======= #
# ======================= #


DATASET_EXTENSIONS = {".csv"}

_s3_client = boto3.client("s3")


# ======================= #
# ======= helpers ======= #
# ======================= #


def _is_s3(path: str) -> bool:
    return path.startswith("s3://")


def _is_metadata(name: str) -> bool:
    return name.endswith(".meta.json")


def _is_dataset(name: str) -> bool:
    return Path(name).suffix in DATASET_EXTENSIONS


def _format_description(metadata: dict) -> str:
    lines: list[str] = []

    name = metadata.get("dataset_name")
    if name:
        lines.append(f"Dataset name: {name}")

    columns = metadata.get("columns", [])
    if columns:
        lines.append("Columns:")
        for col in columns:
            col_name = col.get("col_name", "unknown")
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
    meta_key = f"{key.rsplit('.', 1)[0]}.meta.json"

    try:
        obj = _s3_client.get_object(Bucket=bucket, Key=meta_key)
        metadata = json.loads(obj["Body"].read().decode("utf-8"))
        duck_logger.debug(f"S3 metadata loaded: s3://{bucket}/{meta_key}")
        return _format_description(metadata)

    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchKey":
            duck_logger.error(f"Failed to load S3 metadata: s3://{bucket}/{meta_key}", exc_info=True)
        return f"Dataset name: {Path(key).name}"


def _get_s3_bytes(path: str) -> bytes:
    duck_logger.debug(f"Reading S3 dataset bytes: {path}")

    bucket, key = _split_s3_path(path)
    obj = _s3_client.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()
    return data


def _iter_s3_dataset_keys(bucket: str, prefix: str) -> Iterable[str]:
    paginator = _s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in sorted(page.get("Contents", []), key=lambda o: o["Key"]):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            if _is_metadata(key) or not _is_dataset(key):
                continue
            yield key


def _get_s3_folder_info(path: str) -> list[DatasetInfo]:
    duck_logger.debug(f"Loading S3 folder datasets: {path}")

    bucket, prefix = _split_s3_path(path)
    if not prefix.endswith("/"):
        prefix += "/"

    datasets: list[DatasetInfo] = []

    for key in _iter_s3_dataset_keys(bucket, prefix):
        dataset_path = f"s3://{bucket}/{key}"
        data = _get_s3_bytes(dataset_path)

        datasets.append(
            DatasetInfo(
                filename=Path(key).name,
                description=_get_s3_desc(dataset_path),
                data=data,
                size=len(data),
                source_path=dataset_path,
            )
        )

    return datasets


# ===================== #
# ======= local ======= #
# ===================== #


def _get_local_desc(path: str) -> str:
    """Returns the description of the local file"""
    duck_logger.debug(f"Loading local metadata for dataset: {path}")

    file_path = Path(path)
    meta_path = file_path.with_suffix(".meta.json")

    if not meta_path.exists():
        return f"Dataset name: {file_path.name}"

    try:
        metadata = json.loads(meta_path.read_text())
        duck_logger.debug(f"Local metadata loaded: {meta_path}")
        return _format_description(metadata)

    except Exception:
        duck_logger.error(f"Failed to parse local metadata JSON: {meta_path}", exc_info=True)
        return f"Dataset name: {file_path.name}"


def _get_local_bytes(path: str) -> bytes:
    duck_logger.debug(f"Reading local dataset bytes: {path}")
    data = Path(path).read_bytes()
    return data


def _get_local_folder_info(path: str) -> list[DatasetInfo]:
    duck_logger.debug(f"Loading local folder datasets: {path}")

    folder = Path(path)
    if not folder.is_dir():
        raise ValueError(f"Local path is not a directory: {path}")

    datasets: list[DatasetInfo] = []

    for file_path in sorted(folder.iterdir()):
        if not file_path.is_file():
            continue
        if _is_metadata(file_path.name) or not _is_dataset(file_path.name):
            continue

        data = _get_local_bytes(str(file_path))
        datasets.append(
            DatasetInfo(
                filename=file_path.name,
                description=_get_local_desc(str(file_path)),
                data=data,
                size=len(data),
                source_path=str(file_path),
            )
        )

    return datasets


# ======================== #
# ======== public ======== #
# ======================== #


def determine_mount_case(remote_path: str, target_path: str) -> str:
    """
    Determines the mount case based on path semantics.

    Returns one of:
        - "folder: folder"
        - "file: folder"
        - "file: file"
    """
    if remote_path.endswith("/") and target_path.endswith("/"):
        return "folder: folder"
    if not remote_path.endswith("/") and target_path.endswith("/"):
        return "file: folder"
    if not remote_path.endswith("/") and not target_path.endswith("/"):
        return "file: file"

    duck_logger.warn(f"Invalid mount case - remote path: {remote_path}, target path: {target_path}")
    return ""


def get_folder_info(folder_path: str) -> list[DatasetInfo]:
    return (
        _get_s3_folder_info(folder_path)
        if _is_s3(folder_path)
        else _get_local_folder_info(folder_path)
    )


def get_dataset_info(file_path: str) -> DatasetInfo:
    duck_logger.debug(f"Preparing dataset for mount: {file_path}")

    filename = Path(file_path).name

    if _is_s3(file_path):
        description = _get_s3_desc(file_path)
        data = _get_s3_bytes(file_path)
    else:
        description = _get_local_desc(file_path)
        data = _get_local_bytes(file_path)

    return DatasetInfo(
        filename=filename,
        description=description,
        data=data,
        size=len(data),
        source_path=file_path,
    )


# DEBUG


def debug_list_s3_prefix(path: str, max_keys: int = 1000) -> list[str]:
    """
    Lists all object keys under an S3 prefix for debugging purposes.
    """
    bucket, prefix = _split_s3_path(path)
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    print(f"Listing S3 objects under s3://{bucket}/{prefix}")

    paginator = _s3_client.get_paginator("list_objects_v2")
    keys: list[str] = []

    for page in paginator.paginate(
            Bucket=bucket,
            Prefix=prefix,
            PaginationConfig={"MaxItems": max_keys},
    ):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])

    for key in keys:
        print(f"  s3://{bucket}/{key}")

    if not keys:
        print("No objects found under this prefix.")

    return keys


if __name__ == "__main__":
    debug_list_s3_prefix("s3://stats121-datasets/datasets/")
