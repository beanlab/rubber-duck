import json
from io import StringIO
from pathlib import Path
from typing import TypedDict

import boto3
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
            self._metadata.update(dict(self._load_metadata(location)))

    def _is_s3_location(self, location: str):
        return location.startswith("s3://")

    def _get_s3_info(self, link: str) -> tuple[str, str]:
        link = link.replace("s3://", "").split("/", 1)
        return link[0], link[1] if len(link) > 1 else ""

    def _file_exists(self, path: str, s3: bool, bucket: str = ""):
        if s3:
            try:
                self._s3_client.head_object(Bucket=bucket, Key=path)
                return True
            except Exception as e:
                if e.response['Error']['Code'] == '404':
                    return False
                raise e
        else:
            return Path(path).exists()

    def _load_md_from_json(self, location: str, s3: bool, bucket: str = ""):
        if s3:
            full_location = f"s3://{bucket}/{location}"
            obj = self._s3_client.get_object(Bucket=bucket, Key=location)
            metadata = json.loads(obj['Body'].read().decode('utf-8'))
        else:
            full_location = str(Path(location).resolve())
            with open(location, 'r') as meta_file:
                metadata = json.load(meta_file)
        name = metadata['name']
        columns = [ColumnMetadata(**col) for col in metadata['columns']]
        yield name, DatasetMetadata(location=full_location, name=name, columns=columns)

    def _load_md_from_csv(self, location: str, s3: bool, bucket: str = "", prefix: str = ""):
        name = Path(location).stem if not s3 else location.replace(prefix, '').replace('.csv', '')
        if s3:
            full_location = f"s3://{bucket}/{location}"
            obj = self._s3_client.get_object(Bucket=bucket, Key=location)
            df = pd.read_csv(StringIO(obj['Body'].read().decode('utf-8')), nrows=0)
        else:
            full_location = str(Path(location).resolve())
            df = pd.read_csv(location, nrows=0)
        columns = [ColumnMetadata(name=col, dtype=str(df[col].dtype), description="") for col in df.columns]
        yield name, DatasetMetadata(location=full_location, name=name, columns=columns)

    def _load_metadata(self, location: str):
        if self._is_s3_location(location):
            bucket, prefix = self._get_s3_info(location)
            if not prefix.endswith('/'):
                prefix += '/'
            response = self._s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.csv'):
                    key = str(key)
                    metadata_file = key[:-len('.csv')] + '.meta.json'
                    if self._file_exists(metadata_file, True, bucket):
                        yield from self._load_md_from_json(metadata_file, True, bucket)
                    else:
                        yield from self._load_md_from_csv(key, True, bucket, prefix)
        else:
            for file in Path(location).iterdir():
                if file.is_file() and file.name.endswith('.csv'):
                    metadata_file = str(file.with_suffix('.meta.json'))
                    if self._file_exists(metadata_file, False):
                        yield from self._load_md_from_json(metadata_file, False)
                    else:
                        yield from self._load_md_from_csv(str(file), False)

    def get_dataset_metadata(self) -> dict[str, DatasetMetadata]:
        return self._metadata

    def get_columns_metadata(self, name) -> list[ColumnMetadata]:
        return self._metadata[name].columns

    def get_available_datasets(self) -> list[str]:
        return sorted(list(self._metadata.keys()))

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name in self._loaded_datasets:
            return self._loaded_datasets[name]

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

        raise FileNotFoundError(
            f"Dataset '{name}' not found in local or S3 storage. Available datasets: {self.get_available_datasets()}")

    def clear_cache(self):
        self._loaded_datasets = {}
