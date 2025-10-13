import json
from io import StringIO
from pathlib import Path
from typing import TypedDict, Iterable

import boto3
import botocore.exceptions
import pandas as pd

from ..utils.logger import duck_logger


class ColumnMetadata(TypedDict, total=False):
    name: str
    dtype: str
    description: str
    display_name: str


class DatasetMetadata(TypedDict, total=False):
    location: str
    name: str
    description: str
    columns: list[ColumnMetadata]


class DataStore:
    def __init__(self, locations: list[str]):
        self._loaded_datasets = {}
        self._s3_client = boto3.client("s3")
        self._dataset_locations = locations
        self._metadata: dict[str, DatasetMetadata] = {}
        for location in locations:
            foo = list(self._load_metadata(location))
            self._metadata.update(dict(foo))

    def _load_metadata(self, location: str) -> Iterable:
        if self._is_s3_location(location):
            yield from self._load_md_from_s3(location)
        else:
            yield from self._load_md_from_local(location)

    def _read_md_from_s3_object(self, bucket, obj):
        key = obj["Key"]
        if key.endswith(".csv") or key.endswith(".txt"):
            metadata_file = key[:-4] + ".meta.json"
            if self._s3_file_exists(bucket, metadata_file):
                name, mdata = self._load_md_from_s3_json(bucket, metadata_file, key)
            else:
                name, mdata = self._build_md_from_s3_file(bucket, key)
            mdata['location'] = f's3://{bucket}/{key}'
            yield name, mdata

    def _load_md_from_s3(self, location: str):
        bucket, prefix = self._get_s3_info(location)
        if not prefix.endswith("/"):
            prefix += "/"
        response = self._s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        for obj in response.get("Contents", []):
            try:
                yield from self._read_md_from_s3_object(bucket, obj)
            except Exception:
                duck_logger.exception(f"Error loading metadata from {location}")
                continue

    def _read_md_from_local_file(self, file: Path):
        if file.is_file() and (file.suffix in {".csv", ".txt"}):
            metadata_file = file.with_suffix(".meta.json")
            if metadata_file.exists():
                name, mdata = self._load_md_from_local_json(metadata_file, file)
            else:
                name, mdata = self._build_md_from_local_file(file)
            mdata['location'] = str(file.resolve())
            yield name, mdata

    def _load_md_from_local(self, location: str):
        for file in Path(location).iterdir():
            try:
                yield from self._read_md_from_local_file(file)
            except Exception:
                duck_logger.exception(f"Error loading metadata for {file}")
                continue

    # Metadata loading

    def _build_md_from_s3_file(self, bucket: str, key: str) -> tuple[str, DatasetMetadata]:
        full_location = f"s3://{bucket}/{key}"
        name = key.rsplit(".", 1)[0].split("/")[-1]

        s3_obj = self._s3_client.get_object(Bucket=bucket, Key=key)
        raw = s3_obj["Body"].read()
        df = self._load_dataframe_from_source(raw, Path(key).suffix)

        columns = [
            ColumnMetadata(name=col, dtype=str(df[col].dtype), description="")
            for col in df.columns
        ]
        return name, DatasetMetadata(location=full_location, name=name, columns=columns)

    def _build_md_from_local_file(self, location: Path) -> tuple[str, DatasetMetadata]:
        name = location.stem
        full_location = str(location.resolve())

        df = self._load_dataframe_from_source(location.read_bytes(), location.suffix)

        columns = [
            ColumnMetadata(name=col, dtype=str(df[col].dtype), description="")
            for col in df.columns
        ]
        return name, DatasetMetadata(location=full_location, name=name, columns=columns)

    # Regular loading

    def _load_md_from_s3_json(self, bucket: str, key: str, original_key: str) -> tuple[str, DatasetMetadata]:
        s3_obj = self._s3_client.get_object(Bucket=bucket, Key=key)
        content = s3_obj["Body"].read()
        try:
            content = content.decode('utf-8')

        except UnicodeDecodeError as err:
            try:
                content = content.decode('utf-16')
            except UnicodeDecodeError:
                raise err

        md = json.loads(content)
        return md["name"], md

    def _load_md_from_local_json(self, location: Path, original_location: Path) -> tuple[str, DatasetMetadata]:
        metadata = json.loads(location.read_text())
        return metadata["name"], metadata

    # Data loading

    def _load_dataframe_from_source(self, data: bytes | str, file_suffix: str) -> pd.DataFrame:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        if file_suffix == ".csv":
            return pd.read_csv(StringIO(data))
        elif file_suffix == ".txt":
            return pd.read_csv(StringIO(data), sep=r"\s+", engine="python", quotechar='"')
        else:
            raise ValueError(f"Unsupported file type: {file_suffix}")

    # Utils

    def _rename_columns(self, dataset_name: str, dataframe: pd.DataFrame):
        if self._metadata[dataset_name] is not None:
            column_dict = {}
            for column in self._metadata[dataset_name]["columns"]:
                column_dict[column["name"]] = column["display_name"]
            dataframe.rename(columns=column_dict, inplace=True)
        return dataframe

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name in self._loaded_datasets:
            return self._loaded_datasets[name]

        if name not in self._metadata:
            raise FileNotFoundError(
                f"Dataset '{name}' not found in local or S3 storage. "
                f"Available datasets: {self.get_available_datasets()}"
            )

        try:
            location = self._metadata[name]["location"]

            if self._is_s3_location(location):
                bucket_name, key = self._get_s3_info(location)
                s3_obj = self._s3_client.get_object(Bucket=bucket_name, Key=key)
                raw = s3_obj["Body"].read()
                df = self._load_dataframe_from_source(raw, Path(key).suffix)
            else:
                path = Path(location)
                df = self._load_dataframe_from_source(path.read_bytes(), path.suffix)

            df = self._rename_columns(name, df)

            self._loaded_datasets[name] = df
            return df

        except Exception:
            duck_logger.exception(f"Error loading data for {name}")
            raise

    def get_dataset_metadata(self) -> dict[str, DatasetMetadata]:
        return self._metadata

    def get_columns_metadata(self, name) -> list[ColumnMetadata]:
        try:
            return self._metadata[name]["columns"]
        except KeyError:
            raise KeyError(
                f"Dataset '{name}' not found in metadata. "
                f"Available datasets: {self.get_available_datasets()}"
            )

    def get_available_datasets(self) -> list[str]:
        return sorted(list(self._metadata.keys()))

    def get_column(self, dataset: pd.DataFrame, column: str) -> pd.Series:
        try:
            return dataset[column]
        except KeyError:
            raise KeyError(
                f"Column '{column}' not found in dataset. "
                f"Available columns are: {dataset.columns.tolist()}"
            )

    def clear_cache(self):
        self._loaded_datasets = {}

    # Helpers

    def _is_s3_location(self, location: str):
        return location.startswith("s3://")

    def _get_s3_info(self, link: str) -> tuple[str, str]:
        link = link.replace("s3://", "").split("/", 1)
        return link[0], link[1] if len(link) > 1 else ""

    def _s3_file_exists(self, bucket: str, key: str):
        try:
            self._s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ["404", "NoSuchKey"]:
                return False
            else:
                raise
