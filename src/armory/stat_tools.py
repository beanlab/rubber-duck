import io
from functools import lru_cache

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import skew
from seaborn.external.kde import gaussian_kde

from .tools import register_tool
from ..utils.data_store import get_dataset, get_available_datasets
from ..utils.logger import duck_logger


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

    fallback_messages = {
        "hist": f"{title.split()[0]}s are not appropriate for categorical data",
        "box": f"{title.split()[0]}s are not appropriate for categorical data",
        "dot": f"{title.split()[0]}s are not appropriate for categorical data",
        "pie": f"{title.split()[0]}s are not appropriate for numeric data",
        "proportion": f"{title.split()[0]}s are not appropriate for quantitative data"
    }

    if kind in {"hist", "box", "dot"}:
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

        # Show fallback message for non-numeric in these kinds
        ax.text(0.5, 0.5, fallback_messages[kind], fontsize=12, ha='center', va='center', transform=ax.transAxes)
        ax.tick_params(axis='both', which='both', length=0)

    elif kind == "pie" or kind == "proportion":
        if kind == "pie" or not _is_categorical(data[column]):
            # Show fallback for pie or invalid proportion
            ax.text(0.5, 0.5, fallback_messages[kind], fontsize=12, ha='center', va='center', transform=ax.transAxes)
            ax.axis("off")
        else:
            # Proper categorical proportion bar plot
            counts = data[column].dropna().value_counts()
            proportions = (counts / counts.sum()).reset_index()
            proportions.columns = [column, "Proportion"]
            plt.clf()  # clear figure for new plot
            plt.figure(figsize=(8, 6))
            sns.barplot(data=proportions, x=column, y="Proportion", color="lightblue")
            plt.title(f"Proportion Barplot of {column}")
            plt.ylabel("Proportion")
            plt.xlabel(column)


def _save_plot(name: str) -> tuple[str, io.BytesIO]:
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()
    return name, buffer


def _cache_key(dataset: str, column: str, kind: str) -> str:
    return f"{dataset}_{column}_{kind}.png"

@register_tool
def describe_dataset(dataset: str) -> str:
    """Returns a description of the dataset."""
    duck_logger.debug(f"Used explain_dataset on dataset={dataset}")
    data = get_dataset(dataset)
    return f"Dataset: {dataset}\nNumber of Rows: {len(data)}\nNumber of Columns: {len(data.columns)}\n" \
           f"Columns: {', '.join(data.columns)}"

@register_tool
def explain_capabilities():
    """Returns a description of the bots capabilites."""
    duck_logger.debug("Used explain_capabilities")
    return (
        "This bot can perform a wide range of statistical and visualization tasks on datasets, including:\n"
        "- Generate visualizations: histograms, boxplots, dotplots, barplots, pie charts, and proportion barplots.\n"
        "- Compute statistics: mean, median, mode (via KDE), standard deviation, skewness, and five-number summaries.\n"
        "- Summarize categorical data with frequency tables and proportions.\n"
        "- List available datasets and variable names within datasets.\n"
        "- Provide descriptions and metadata for datasets.\n\n"
        "It supports both numeric and categorical columns, and handles inappropriate column types with informative fallback messages."
    )

@register_tool
def get_dataset_names() -> str:
    """Returns a list of all available datasets."""
    duck_logger.debug("Used get_available_datasets")
    datasets = get_available_datasets()
    return f"Available datasets: {', '.join(datasets)}"

@register_tool
def get_variable_names(dataset: str) -> str:
    """Returns a list of all variable names in the dataset."""
    duck_logger.debug(f"Used get_variable_names on dataset={dataset}")
    data = get_dataset(dataset).columns.to_list()
    return f"Variable names in {dataset}: {', '.join(data)}"


@register_tool
def plot_histogram(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    return _cached_histogram(dataset, column)


@lru_cache(maxsize=128)
def _cached_histogram(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    duck_logger.debug(f"Generating histogram plot (cached) for {dataset}.{column}")
    data = get_dataset(dataset)
    name = _cache_key(dataset, column, "histogram") + ".png"

    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found in dataset.")

    if _is_categorical(data[column]):
        _plot_message_with_axes(data, column, f"Histogram of {column}", "hist")
    else:
        plt.figure(figsize=(8, 6))
        sns.histplot(data[column], kde=True, bins=20)
        plt.title(f"Histogram of {column}")
        plt.xlabel(column)
        plt.ylabel("Frequency")

    return _save_plot(name)


@register_tool
def plot_boxplot(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    return _cached_boxplot(dataset, column)

@lru_cache(maxsize=128)
def _cached_boxplot(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    duck_logger.debug(f"Generating boxplot (cached) for {dataset}.{column}")
    data = get_dataset(dataset)
    name = _cache_key(dataset, column, "boxplot") + ".png"

    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found.")

    if _is_categorical(data[column]):
        _plot_message_with_axes(data, column, f"Boxplot of {column}", "box")
    else:
        plt.figure(figsize=(8, 6))
        sns.boxplot(y=data[column])
        plt.title(f"Boxplot of {column}")
        plt.ylabel(column)

    return _save_plot(name)

@register_tool
def plot_dotplot(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    return _cached_dotplot(dataset, column)

@lru_cache(maxsize=128)
def _cached_dotplot(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    duck_logger.debug(f"Generating dotplot (cached) for {dataset}.{column}")
    data = get_dataset(dataset)
    name = _cache_key(dataset, column, "dotplot") + ".png"

    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found.")

    if _is_categorical(data[column]):
        _plot_message_with_axes(data, column, f"Dotplot of {column}", "dot")
    else:
        plt.figure(figsize=(8, 6))
        sns.stripplot(x=data[column], jitter=True)
        plt.title(f"Dotplot of {column}")
        plt.xlabel(column)

    return _save_plot(name)



@register_tool
def plot_barplot(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    return _cached_barplot(dataset, column)

@lru_cache(maxsize=128)
def _cached_barplot(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    duck_logger.debug(f"Generating barplot (cached) for {dataset}.{column}")
    data = get_dataset(dataset)
    name = _cache_key(dataset, column, "barplot") + ".png"

    if column not in data.columns.to_list():
        raise ValueError(f"Column '{column}' not found.")

    value_counts = data[column].value_counts()
    plt.figure(figsize=(8, 6))
    sns.barplot(x=value_counts.index, y=value_counts.values)
    plt.title(f"Barplot of {column}")
    plt.xlabel(column)
    plt.ylabel("Count")

    return _save_plot(name)


@register_tool
def plot_pie_chart(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    return _cached_pie_chart(dataset, column)

@lru_cache(maxsize=128)
def _cached_pie_chart(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    duck_logger.debug(f"Generating pie chart (cached) for {dataset}.{column}")
    data = get_dataset(dataset)
    name = _cache_key(dataset, column, "piechart") + ".png"

    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found.")

    if not _is_categorical(data[column]):
        _plot_message_with_axes(data, column, f"Pie Chart of {column}", "dot")
    else:
        value_counts = data[column].dropna().value_counts()
        labels = [f"{label} ({round(p * 100, 1)}%)" for label, p in (value_counts / value_counts.sum()).items()]
        plt.figure(figsize=(8, 6))
        plt.pie(value_counts.values, labels=labels, colors=sns.color_palette("pastel"), startangle=140,
                autopct='%1.1f%%')
        plt.title(f"Pie Chart of {column}")
        plt.axis("equal")

    return _save_plot(name)

@register_tool
def plot_proportion_barplot(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    return _cached_proportion_barplot(dataset, column)


@lru_cache(maxsize=128)
def _cached_proportion_barplot(dataset: str, column: str) -> tuple[str, io.BytesIO]:
    duck_logger.debug(f"Generating proportion barplot (cached) for {dataset}.{column}")
    data = get_dataset(dataset)

    name = f"{dataset}_{column}_proportion_barplot.png"
    title = f"Proportion Barplot of {column}"

    # Let the enhanced plot message function handle fallback or actual plot
    _plot_message_with_axes(data, column, title, kind="proportion")

    return _save_plot(name)

@register_tool
def calculate_mean(dataset: str, column: str) -> str:
    """Calculates the mean of a numeric column in the dataset, if not categorical."""
    duck_logger.debug(f"Calculating mean for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "Mean cannot be calculated for categorical data"
    return f"Mean = {round(series.dropna().mean(), 4)}"


@register_tool
def calculate_skewness(dataset: str, column: str) -> str:
    """Calculates the skewness (asymmetry) of a numeric column in the dataset."""
    duck_logger.debug(f"Calculating skewness for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "Skewness cannot be calculated for categorical data"
    return f"Skewness = {round(skew(series.dropna()), 4)}"


@register_tool
def calculate_std(dataset: str, column: str) -> str:
    """Calculates the standard deviation of a numeric column in the dataset."""
    duck_logger.debug(f"Calculating standard deviation for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "Standard Deviation cannot be calculated for categorical data"
    return f"Standard Deviation = {round(series.dropna().std(), 4)}"


@register_tool
def calculate_median(dataset: str, column: str) -> str:
    """Calculates the median (middle value) of a numeric column in the dataset."""
    duck_logger.debug(f"Calculating median for: {column} in dataset: {dataset}")
    data = get_dataset(dataset)
    series = data[column]
    if _is_categorical(series):
        return "Median cannot be calculated for categorical data"
    return f"Median = {round(series.dropna().median(), 4)}"


@register_tool
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


@register_tool
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


@register_tool
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


@register_tool
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
