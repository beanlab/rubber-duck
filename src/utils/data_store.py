from io import StringIO
from pathlib import Path
import boto3
import pandas as pd
from botocore.exceptions import ClientError


class DataStore:
    def __init__(self, locations: list[str]):
        self._loaded_datasets = {}
        self._s3_client = boto3.client('s3')
        self._file_locations = locations

    def _get_local_and_s3_locations(self) -> tuple[list[Path], list[str]]:
        local_locations = []
        s3_locations = []
        for location in self._file_locations:
            if location.startswith("s3://"):
                s3_locations.append(location)
            else:
                local_locations.append(Path(location))
        return local_locations, s3_locations

    def _get_s3_info(self, link: str) -> tuple[str, str]:
        link = link.replace("s3://", "").split("/", 1)
        bucket_name = link[0]
        folder = link[1] if len(link) > 1 else ""
        if not folder.endswith("/"):
            folder += "/"
        return bucket_name, folder

    def get_available_datasets(self) -> list[str]:
        datasets = set()
        local_locations, s3_locations = self._get_local_and_s3_locations()

        for folder_path in local_locations:
            try:
                for f in folder_path.iterdir():
                    if f.is_file() and f.name.endswith(".csv"):
                        datasets.add(f.stem)
            except FileNotFoundError:
                continue  # In case the folder doesn't exist

        for s3_path in s3_locations:
            bucket_name, folder = self._get_s3_info(s3_path)
            try:
                response = self._s3_client.list_objects_v2(Bucket=bucket_name, Prefix=folder)
                for obj in response.get('Contents', []):
                    key = obj['Key']
                    if key.endswith(".csv"):
                        name = key.replace(folder, "").replace(".csv", "")
                        if "/" not in name:  # Only top-level files
                            datasets.add(name)
            except ClientError:
                continue

        return sorted(datasets)

    def get_dataset_local(self, name: str, folder_path: Path) -> pd.DataFrame:
        datasets = {f.name: f for f in Path(folder_path).iterdir() if f.is_file()}
        if f"{name}.csv" not in datasets:
            raise ValueError(f"Dataset '{name}' not found in {folder_path}")
        return pd.read_csv(datasets[f"{name}.csv"])

    def get_dataset_s3(self, name: str, link: str) -> pd.DataFrame:
        bucket_name, folder = self._get_s3_info(link)
        object_key = f"{folder}{name}.csv"
        try:
            response = self._s3_client.get_object(Bucket=bucket_name, Key=object_key)
            csv_string = response['Body'].read().decode('utf-8')
            return pd.read_csv(StringIO(csv_string))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"Dataset '{name}' not found in S3 path {link}.")
            else:
                raise

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name in self._loaded_datasets:
            return self._loaded_datasets[name]

        local_locations, s3_locations = self._get_local_and_s3_locations()

        for folder_path in local_locations:
            available = [f.stem for f in folder_path.glob("*.csv")]
            if name in available:
                df = self.get_dataset_local(name, folder_path)
                self._loaded_datasets[name] = df
                return df

        for s3_path in s3_locations:
            available = self.get_available_datasets()
            if name in available:
                df = self.get_dataset_s3(name, s3_path)
                self._loaded_datasets[name] = df
                return df

        raise FileNotFoundError(f"Dataset '{name}' not found in local or S3 storage.")

    def clear_cache(self):
        self._loaded_datasets = {}
