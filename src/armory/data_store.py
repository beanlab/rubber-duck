import json
from io import StringIO
from pathlib import Path
from typing import TypedDict, Iterable

import boto3
import botocore.exceptions
import pandas as pd


class ColumnMetadata(TypedDict):
    name: str
    dtype: str
    description: str


class DatasetMetadata(TypedDict):
    location: str
    name: str
    columns: list[ColumnMetadata]


class DataStore:
    def __init__(self, locations: list[str]):
        self._loaded_datasets = {}
        self._s3_client = boto3.client('s3')
        self._dataset_locations = locations
        self._metadata = {}
        for location in locations:
            foo = list(self._load_metadata(location))
            self._metadata.update(dict(foo))

    def _load_metadata(self, location: str) -> Iterable:
        if self._is_s3_location(location):
            yield from self._load_md_from_s3(location)
        else:
            yield from self._load_md_from_local(location)

    def _read_md_from_s3_object(self, bucket, obj):
        key = obj['Key']
        if key.endswith('.csv'):
            key = str(key)
            metadata_file = key[:-len('.csv')] + '.meta.json'
            if self._s3_file_exists(bucket, metadata_file):
                yield self._load_md_from_s3_json(bucket, metadata_file)
            else:
                yield self._load_md_from_s3_csv(bucket, key)

    def _load_md_from_s3(self, location: str):
        bucket, prefix = self._get_s3_info(location)
        if not prefix.endswith('/'):
            prefix += '/'
        response = self._s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        for obj in response.get('Contents', []):
            yield from self._read_md_from_s3_object(bucket, obj)

    def _read_md_from_local_file(self, file):
        if file.is_file() and file.name.endswith('.csv'):
            metadata_file = file.with_suffix('.meta.json')
            if metadata_file.exists():
                yield self._load_md_from_local_json(metadata_file)
            else:
                yield self._load_md_from_local_csv(file)

    def _load_md_from_local(self, location: str):
        for file in Path(location).iterdir():
            yield from self._read_md_from_local_file(file)

    def _load_md_from_s3_json(self, bucket: str, obj: str) -> tuple[str, DatasetMetadata]:
        obj = self._s3_client.get_object(Bucket=bucket, Key=obj)
        md = json.loads(obj['Body'].read().decode('utf-8'))
        md['location'] = f"s3://{bucket}/{obj}"
        return md['name'], md

    def _load_md_from_local_json(self, location: Path) -> tuple[str, DatasetMetadata]:
        metadata = json.loads(location.read_text())
        metadata['location'] = str(location.resolve())
        return metadata['name'], metadata

    def _load_md_from_s3_csv(self, bucket: str, obj: str) -> tuple[str, DatasetMetadata]:
        full_location = f"s3://{bucket}/{obj}"
        name = obj.replace('.csv', '').split('/')[-1]

        obj = self._s3_client.get_object(Bucket=bucket, Key=obj)
        df = pd.read_csv(StringIO(obj['Body'].read().decode('utf-8')), nrows=0)
        columns = [
            ColumnMetadata(name=col, dtype=str(df[col].dtype), description="")
            for col in df.columns
        ]
        return name, DatasetMetadata(location=full_location, name=name, columns=columns)

    def _load_md_from_local_csv(self, location: Path) -> tuple[str, DatasetMetadata]:
        name = location.stem
        full_location = str(Path(location).resolve())
        df = pd.read_csv(location, nrows=0)
        columns = [
            ColumnMetadata(name=col, dtype=str(df[col].dtype), description="")
            for col in df.columns
        ]
        return name, DatasetMetadata(location=full_location, name=name, columns=columns)

    def _is_s3_location(self, location: str):
        return location.startswith("s3://")

    def _get_s3_info(self, link: str) -> tuple[str, str]:
        link = link.replace("s3://", "").split("/", 1)
        return link[0], link[1] if len(link) > 1 else ""

    def _s3_file_exists(self, bucket: str, obj: str):
        try:
            self._s3_client.head_object(Bucket=bucket, Key=obj)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['404', 'NoSuchKey']:
                return False
            else:
                raise e

    def get_dataset_metadata(self) -> dict[str, DatasetMetadata]:
        return self._metadata

    def get_columns_metadata(self, name) -> list[ColumnMetadata]:
        try:
            return self._metadata[name]['columns']
        except KeyError:
            raise KeyError(
                f"Dataset '{name}' not found in metadata. Available datasets: {self.get_available_datasets()}")

    def get_available_datasets(self) -> list[str]:
        return sorted(list(self._metadata.keys()))

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name in self._loaded_datasets:
            return self._loaded_datasets[name]

        try:
            if self._metadata[name]:
                location = self._metadata[name]['location']
                if self._is_s3_location(location):
                    bucket_name, key = self._get_s3_info(location)
                    csv_obj = self._s3_client.get_object(Bucket=bucket_name, Key=key)
                    df = pd.read_csv(StringIO(csv_obj['Body'].read().decode('utf-8')))
                else:
                    df = pd.read_csv(location)

                self._loaded_datasets[name] = df
                return df
        except KeyError:
            raise KeyError(
                f"Dataset '{name}' not found in metadata. Available datasets: {self.get_available_datasets()}")

        raise FileNotFoundError(
            f"Dataset '{name}' not found in local or S3 storage. Available datasets: {self.get_available_datasets()}")

    def get_column(self, dataset: pd.DataFrame, column: str) -> pd.Series:
        try:
            return dataset[column]
        except KeyError:
            raise KeyError(
                f"Column '{column}' not found in dataset. Available columns are: {dataset.columns.tolist()}")

    def clear_cache(self):
        self._loaded_datasets = {}
