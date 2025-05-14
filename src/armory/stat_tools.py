import hashlib
import os
from pathlib import Path

import pandas as pd
import numpy as np
from agents import function_tool
from openai import AsyncOpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError

from ..conversation.conversation import RetryableException
from ..utils.logger import duck_logger
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import skew, gaussian_kde
from ..utils.data_store import get_dataset

OUTPUT_DIR = Path("generated_images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def _is_categorical(series) -> bool:
    if isinstance(series, list) or isinstance(series, dict):
        series = pd.Series(series)
    if not isinstance(series, pd.Series):
        raise ValueError(f"Expected a pandas Series, got {type(series)}")
    return series.dtype == object or pd.api.types.is_categorical_dtype(series)

def _plot_message_with_axes(data: pd.DataFrame, column: str, title: str, kind: str):
    plt.figure(figsize=(8, 6))
    ax = plt.gca()
    ax.set_title(title, fontsize=14)

    values = pd.to_numeric(data[column], errors='coerce').dropna()

    if kind == "hist":
        ax.set_xlim(values.min(), values.max())
        ax.set_ylim(0, 1)
        ax.set_xlabel(column)
        ax.set_ylabel("Frequency")
    elif kind == "box":
        ax.set_ylim(values.min(), values.max())
        ax.set_xlim(-1, 1)
        ax.set_ylabel(column)
    elif kind == "dot":
        ax.set_xlim(values.min(), values.max())
        ax.set_ylim(0, 1)
        ax.set_xlabel(column)

    ax.text(0.5, 0.5, f"{title.split()[0]}s are not appropriate for categorical data", fontsize=12, ha='center', va='center', transform=ax.transAxes)
    ax.tick_params(axis='both', which='both', length=0)

def _generate_cache_key(*args):
    """Generate a cache key based on the function name and arguments."""
    key_str = "_".join(str(arg) for arg in args)
    return hashlib.md5(key_str.encode()).hexdigest()

def _save_plot(file_path: Path) -> Path:
    plt.savefig(file_path, format="png")
    plt.close()
    duck_logger.debug(f"Saved plot to {file_path}")
    return file_path

def _cached_path(dataset: str, column: str, kind: str) -> Path:
    cache_key = _generate_cache_key(dataset, column, kind)
    return OUTPUT_DIR / f"{cache_key}.png"

@function_tool
def get_variable_names(dataset: str) -> list[str]:
    """Returns the variable names (columns) of the dataset."""
    duck_logger.debug(f"Used get_variable_names on dataset={dataset}")
    data = get_dataset(dataset)
    return data.columns.to_list()

@function_tool
def get_column_data(dataset: str, column: str) -> pd.Series:
    """Returns the data of a specific column in the dataset."""
    data = get_dataset(dataset)
    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found. Available: {list(data.columns)}")
    return data[column]


@function_tool
def plot_histogram(dataset: str, column: str) -> Path:
    """Generates a histogram with KDE for the specified numeric column in a dataset, or a message image if the column is categorical."""
    duck_logger.debug(f"Used plot_histogram on dataset={dataset}, column={column}")
    data = get_dataset(dataset)
    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found. Available: {list(data.columns)}")

    output_path = _cached_path(dataset, column, "histogram")
    if output_path.exists():
        duck_logger.debug(f"Using cached histogram at {output_path}")
        return output_path


    if _is_categorical(data[column]):
        _plot_message_with_axes(data, column, f"Histogram of {column}", "hist")
    else:
        plt.figure(figsize=(8, 6))
        sns.histplot(data[column], kde=True, bins=20)
        plt.title(f"Histogram of {column}")
        plt.xlabel(column)
        plt.ylabel("Frequency")
    return _save_plot(output_path)

@function_tool
def plot_boxplot(dataset: str, column: str) -> Path:
    """Creates a boxplot of the specified numeric column in a dataset, or a message image if the column is categorical."""
    duck_logger.debug(f"Used plot_boxplot on dataset={dataset}, column={column}")
    data = get_dataset(dataset)
    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found. Available: {list(data.columns)}")

    output_path = _cached_path(dataset, column, "boxplot")

    if output_path.exists():
        duck_logger.debug(f"Using cached histogram at {output_path}")
        return output_path

    if _is_categorical(data[column]):
        _plot_message_with_axes(data, column, f"Boxplot of {column}", "box")
    else:
        plt.figure(figsize=(8, 6))
        sns.boxplot(y=data[column])
        plt.title(f"Boxplot of {column}")
        plt.ylabel(column)
    return _save_plot(output_path)

@function_tool
def plot_dotplot(dataset: str, column: str) -> Path:
    """Creates a dot plot (strip plot) for the specified numeric column, or a message image if the column is categorical."""
    duck_logger.debug(f"Used plot_dotplot on dataset={dataset}, column={column}")
    data = get_dataset(dataset)
    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found. Available: {list(data.columns)}")

    output_path = _cached_path(dataset, column, "dotplot")

    if output_path.exists():
        duck_logger.debug(f"Using cached histogram at {output_path}")
        return output_path

    if _is_categorical(data[column]):
        _plot_message_with_axes(data, column, f"Dotplot of {column}", "dot")
    else:
        plt.figure(figsize=(8, 6))
        sns.stripplot(x=data[column], jitter=True)
        plt.title(f"Dotplot of {column}")
        plt.xlabel(column)
    return _save_plot(output_path)

@function_tool
def plot_barplot(dataset: str, column: str) -> Path:
    """Creates a bar plot of value counts for a categorical column in the dataset."""
    duck_logger.debug(f"Used plot_barplot on dataset={dataset}, column={column}")
    data = get_dataset(dataset)
    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found. Available: {list(data.columns)}")

    output_path = _cached_path(dataset, column, "barplot")

    if output_path.exists():
        duck_logger.debug(f"Using cached histogram at {output_path}")
        return output_path

    plt.figure(figsize=(8, 6))
    sns.barplot(x=data[column].value_counts().index, y=data[column].value_counts().values)
    plt.title(f"Barplot of {column}")
    plt.xlabel(column)
    plt.ylabel("Count")
    return _save_plot(output_path)

@function_tool
def plot_pie_chart(dataset: str, column: str) -> Path:
    """Creates a pie chart of value proportions for a categorical column, or a message image if the column is numeric."""
    duck_logger.debug(f"Used plot_pie_chart on dataset={dataset}, column={column}")
    data = get_dataset(dataset)
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found. Available: {list(data.columns)}")

    output_path = _cached_path(dataset, column, "piechart")

    if output_path.exists():
        duck_logger.debug(f"Using cached pie chart at {output_path}")
        return output_path

    if not _is_categorical(data[column]):
        _plot_message_with_axes(data, column, f"Pie Chart of {column}", "dot")
    else:
        value_counts = data[column].dropna().value_counts()
        labels = [f"{label} ({round(p * 100, 1)}%)" for label, p in (value_counts / value_counts.sum()).items()]
        plt.figure(figsize=(8, 6))
        plt.pie(value_counts.values, labels=labels, colors=sns.color_palette("pastel"), startangle=140, autopct='%1.1f%%')
        plt.title(f"Pie Chart of {column}")
        plt.axis("equal")
    return _save_plot(output_path)


@function_tool
def calculate_mean(dataset: str, column: str) -> str:
    """Calculates the mean of a numeric column in the dataset, if not categorical."""
    duck_logger.debug(f"Calculating mean for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "Mean cannot be calculated for categorical data"
    return f"Mean = {round(series.dropna().mean(), 4)}"

@function_tool
def calculate_skewness(dataset: str, column: str) -> str:
    """Calculates the skewness (asymmetry) of a numeric column in the dataset."""
    duck_logger.debug(f"Calculating skewness for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "Skewness cannot be calculated for categorical data"
    return f"Skewness = {round(skew(series.dropna()), 4)}"

@function_tool
def calculate_std(dataset: str, column: str) -> str:
    """Calculates the standard deviation of a numeric column in the dataset."""
    duck_logger.debug(f"Calculating standard deviation for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "Standard Deviation cannot be calculated for categorical data"
    return f"Standard Deviation = {round(series.dropna().std(), 4)}"

@function_tool
def calculate_median(dataset: str, column: str) -> str:
    """Calculates the median (middle value) of a numeric column in the dataset."""
    duck_logger.debug(f"Calculating median for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "Median cannot be calculated for categorical data"
    return f"Median = {round(series.dropna().median(), 4)}"

@function_tool
def calculate_mode(dataset: str, column: str) -> str:
    """Estimates the mode of a numeric column using the peak of a KDE (kernel density estimate)."""
    duck_logger.debug(f"Calculating approximate mode (KDE) for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column].dropna()

    if _is_categorical(series):
        return "Mode cannot be calculated for categorical data"
    if series.empty:
        return "No valid values to calculate mode"
    try:
        kde = gaussian_kde(series)
        x_vals = np.linspace(series.min(), series.max(), 1000)
        y_vals = kde(x_vals)
        mode_est = x_vals[np.argmax(y_vals)]
        return f"(Approximate) Mode = {round(mode_est, 4)}"
    except Exception as e:
        duck_logger.error(f"Error in KDE-based mode estimation: {e}")
        return "Error calculating mode"

@function_tool
def calculate_five_number_summary(dataset: str, column: str) -> str:
    """Returns the five-number summary (min, Q1, median, Q3, max) for a numeric column in the dataset."""
    duck_logger.debug(f"Calculating five-number summary for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "5 Number Summary cannot be calculated for categorical data"
    summary = series.dropna().quantile([0, 0.25, 0.5, 0.75, 1.0])
    labels = ["Min", "Q1", "Median", "Q3", "Max"]
    return "; ".join(f"{label}={round(val, 4)}" for label, val in zip(labels, summary))

@function_tool
def calculate_table_of_counts(dataset: str, column: str) -> dict | str:
    """Returns a frequency table (category counts) for a categorical column in the dataset."""
    duck_logger.debug(f"Calculating table of counts for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if not _is_categorical(series):
        return "Table of Counts cannot be calculated for quantitative data"
    counts = series.value_counts(dropna=True).reset_index()
    counts.columns = ["Category", "Count"]
    return counts.to_dict(orient="records")

@function_tool
def calculate_proportions(dataset: str, column: str) -> dict | str:
    """Returns the relative proportions of each category in a categorical column of the dataset."""
    duck_logger.debug(f"Calculating proportions for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if not _is_categorical(series):
        return "Proportions can only be calculated for categorical data"
    proportions = (series.value_counts(normalize=True, dropna=True).round(4).reset_index())
    proportions.columns = ["Category", "Proportion"]
    return proportions.to_dict(orient="records")
