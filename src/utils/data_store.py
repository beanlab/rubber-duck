from io import StringIO
from pathlib import Path

import boto3
import pandas as pd


class ColumnMetadata:
    def __init__(self, name: str, dtype: str):
        self.name = name
        self.dtype = dtype


class DatasetMetadata():
    def __init__(self, location: str, name: str, columns: list[ColumnMetadata]):
        self.location = location
        self.name = name
        self.columns = columns


class DataStore:
    def __init__(self, locations: list[str]):
        self._loaded_datasets = {}
        self._s3_client = boto3.client('s3')
        self._file_locations = locations
        self._metadata = {}
        for location in locations:
            self._metadata.update(dict(self._load_metadata(location)))

    def _is_s3_location(self, location: str):
        return location.startswith("s3://")

    def _load_metadata(self, location: str):
        if self._is_s3_location(location):
            return self._load_s3_metadata(location)

        else:
            return self._load_local_metadata(location)

    def _get_s3_info(self, link: str) -> tuple[str, str]:
        link = link.replace("s3://", "").split("/", 1)
        bucket_name = link[0]
        folder = link[1] if len(link) > 1 else ""
        return bucket_name, folder

    def _load_s3_metadata(self, location: str):
        bucket_name, folder = self._get_s3_info(location)
        if not folder.endswith('/'):
            folder += '/'
        response = self._s3_client.list_objects_v2(Bucket=bucket_name, Prefix=folder)
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('.csv'):
                full_location = f"s3://{bucket_name}/{key}"
                name = key.replace(folder, '').replace('.csv', '')
                csv_obj = self._s3_client.get_object(Bucket=bucket_name, Key=key)
                df = pd.read_csv(StringIO(csv_obj['Body'].read().decode('utf-8')), nrows=0)
                columns = [ColumnMetadata(name=col, dtype=str(df[col].dtype)) for col in df.columns]
                yield name, DatasetMetadata(location=full_location, name=name, columns=columns)

    def _load_local_metadata(self, location: str):
        for file in Path(location).iterdir():
            if file.is_file() and file.name.endswith('.csv'):
                full_location = str(file.resolve())
                name = file.stem
                df = pd.read_csv(file, nrows=0)
                columns = [ColumnMetadata(name=col, dtype=str(df[col].dtype)) for col in df.columns]
                yield name, DatasetMetadata(location=full_location, name=name, columns=columns)

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
            location = self._metadata[name].location
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
