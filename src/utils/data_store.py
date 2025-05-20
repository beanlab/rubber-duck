import os
from io import StringIO

import boto3
import pandas as pd

from botocore.exceptions import ClientError

_loaded_datasets = {}

s3 = boto3.client('s3')
bucket_name = 'stats121-datasets'
folder = 'datasets/'

def get_dataset(name: str) -> pd.DataFrame:
    object_key = f"{folder}{name}.csv"

    if name in _loaded_datasets:
        return _loaded_datasets[name]
    try:
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        csv_string = response['Body'].read().decode('utf-8')
        df = pd.read_csv(StringIO(csv_string))
        _loaded_datasets[name] = df
        return df
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            datasets = get_available_datasets()
            raise FileNotFoundError(
                f"Dataset '{name}' not found in bucket '{bucket_name}', available datasets are {datasets}.")
        else:
            raise


def get_available_datasets() -> list[str]:
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder)
    dataset_names = [
        obj['Key'].replace(f"{folder}/", "").replace(".csv", "")
        for obj in response.get('Contents', [])
        if obj['Key'].endswith('.csv')
    ]
    return dataset_names

def clear_cache():
    global _loaded_datasets
    _loaded_datasets = {}


