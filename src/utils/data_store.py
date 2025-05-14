import pandas as pd
import os

# Construct path relative to the project root
ADMISSIONS = os.path.join(os.path.dirname(__file__), '..', '..', 'datasets', 'admissions.csv')
GESTATIONAL = os.path.join(os.path.dirname(__file__), '..', '..', 'datasets', 'gestational.csv')
CARPRICE = os.path.join(os.path.dirname(__file__), '..', '..', 'datasets', 'carprice.csv')

# Load the DataFrame once

_loaded_datasets = {}

def get_dataset(name: str) -> pd.DataFrame:
    if name in _loaded_datasets:
        return _loaded_datasets[name]

    datasets = {"admissions": ADMISSIONS, "gestational": GESTATIONAL, "carprice": CARPRICE}
    if name not in datasets:
        raise ValueError(f"Dataset '{name}' not found. Available: {list(datasets.keys())}")

    df = pd.read_csv(datasets[name])
    _loaded_datasets[name] = df
    return df
