import pandas as pd
import pathlib


BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "datasets"

ADMISSIONS = DATA_DIR / "admissions.csv"
GESTATIONAL = DATA_DIR / "gestational.csv"
CARPRICE = DATA_DIR / "carprice.csv"

_loaded_datasets = {}
datasets = {"admissions": ADMISSIONS, "gestational": GESTATIONAL, "carprice": CARPRICE}

def get_dataset(name: str) -> pd.DataFrame:
    if name in _loaded_datasets:
        return _loaded_datasets[name]

    if name not in datasets:
        raise ValueError(f"Dataset '{name}' not found. Available: {list(datasets.keys())}")

    df = pd.read_csv(datasets[name])
    _loaded_datasets[name] = df
    return df

def get_available_datasets() -> list[str]:
    return list(datasets.keys())