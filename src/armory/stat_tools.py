import io
from typing import Optional, Literal, Callable, Coroutine, Awaitable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from scipy.stats import skew, norm, ttest_1samp, t, chi2_contingency
from seaborn.external.kde import gaussian_kde
from sklearn.model_selection import KFold
from sklearn.metrics import mean_squared_error
import statsmodels.formula.api as smf

from .cache import cache_result
from .tools import register_tool, direct_send_message
from ..armory.data_store import DataStore
from ..utils.logger import duck_logger


class StatsTools:
    def __init__(self, datastore: DataStore, autocorrect: Callable[[list[str], str], Awaitable[str]]):
        self._datastore = datastore
        self._autocorrect = autocorrect

    def _is_categorical(self, series) -> bool:
        if isinstance(series, list) or isinstance(series, dict):
            series = pd.Series(series)
        return series.dtype == object or pd.api.types.is_categorical_dtype(series)

    def _plot_message_with_axes(self, data: pd.DataFrame, column: str, title: str, kind: str):
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
            if kind == "pie" or not self._is_categorical(data[column]):
                # Show fallback for pie or invalid proportion
                ax.text(0.5, 0.5, fallback_messages[kind], fontsize=12, ha='center', va='center',
                        transform=ax.transAxes)
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

    def _save_plot(self, name: str) -> tuple[str, bytes]:
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        plt.close()
        return name, buffer.read()

    def _photo_name(self, *args) -> str:
        return "_".join(str(arg) for arg in args if arg) + ".png"

    @register_tool
    def describe_dataset(self, dataset: str) -> str:
        """Returns a description of the dataset."""
        duck_logger.debug(f"Used describe_dataset on dataset={dataset}")
        data = self._datastore.get_columns_metadata(dataset)
        data_expanded = [
            f"Column Name: {col['name']}, Column Data Type {col['dtype']}. Column Description: {col['description']}" for
            col in data]
        return " ".join(data_expanded) if data_expanded else "No columns found in dataset."

    @register_tool
    def explain_capabilities(self):
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
    def get_dataset_names(self) -> str:
        """Returns a list of all available datasets."""
        duck_logger.debug("Used get_available_datasets")
        datasets = self._datastore.get_available_datasets()
        return f"Available datasets: {', '.join(datasets)}"

    @register_tool
    async def get_variable_names(self, dataset: str) -> str:
        """Returns a list of all variable names in the dataset."""
        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)
        duck_logger.debug(f"Used get_variable_names on dataset={dataset}")
        data = self._datastore.get_dataset(dataset).columns.to_list()
        return f"Variable names in {dataset}: {', '.join(data)}"

    @register_tool
    @direct_send_message
    @cache_result
    async def show_dataset_head(self, dataset: str, n: int) -> tuple[str, bytes] | str:
        """Shows the first n rows of the dataset as a table image."""
        duck_logger.debug(f"Generating head preview for {dataset} with n={n}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if not isinstance(n, int) or n <= 0:
            return "n must be a positive integer."

        df = data.head(n)

        # Wrap long column names with line breaks at ~12 chars
        def wrap_colname(name, width=12):
            import textwrap
            return '\n'.join(textwrap.wrap(name, width))

        wrapped_cols = [wrap_colname(str(col)) for col in df.columns]

        fig_width = min(12, len(df.columns) * 2)
        fig_height = 0.6 * (n + 1)

        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.axis("off")

        table = ax.table(
            cellText=df.values,
            colLabels=wrapped_cols,
            loc="center",
            cellLoc="center",
        )

        table.auto_set_font_size(False)
        table.set_fontsize(10)

        # Adjust column widths proportionally
        n_cols = len(df.columns)
        for i in range(n_cols):
            table.auto_set_column_width(i)

        buf = io.BytesIO()
        name = f"{dataset}_head_{n}_rows.png"

        plt.tight_layout()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        buf.seek(0)

        return name, buf.read()

    # Tools for dataset statistics and visualizations
    @register_tool
    @direct_send_message
    @cache_result
    async def plot_histogram(self, dataset: str, column: str) -> tuple[str, bytes]:
        """Generate a histogram for the specified dataset column."""
        duck_logger.debug(f"Generating histogram plot for {dataset}.{column}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "histogram")

        if column not in data.columns.to_list():
            column = await self._autocorrect(data.columns.to_list(), column)

        if self._is_categorical(data[column]):
            self._plot_message_with_axes(data, column, f"Histogram of {column}", "hist")
        else:
            plt.figure(figsize=(8, 6))
            sns.histplot(data[column], kde=True, bins=20)
            plt.title(f"Histogram of {column}")
            plt.xlabel(column)
            plt.ylabel("Frequency")

        return self._save_plot(name)

    @register_tool
    @direct_send_message
    @cache_result
    async def plot_boxplot(self, dataset: str, column: str) -> tuple[str, bytes]:
        """Generate a boxplot for the specified dataset column."""
        duck_logger.debug(f"Generating boxplot for {dataset}.{column}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "boxplot")

        if column not in data.columns.to_list():
            column = await self._autocorrect(data.columns.to_list(), column)

        if self._is_categorical(data[column]):
            self._plot_message_with_axes(data, column, f"Boxplot of {column}", "box")
        else:
            plt.figure(figsize=(8, 6))
            sns.boxplot(y=data[column])
            plt.title(f"Boxplot of {column}")
            plt.ylabel(column)

        return self._save_plot(name)

    @register_tool
    @direct_send_message
    @cache_result
    async def plot_dotplot(self, dataset: str, column: str) -> tuple[str, bytes]:
        """Generate a dotplot for the specified dataset column."""
        duck_logger.debug(f"Generating dotplot for {dataset}.{column}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "dotplot")

        if column not in data.columns.to_list():
            column = await self._autocorrect(data.columns.to_list(), column)

        if self._is_categorical(data[column]):
            self._plot_message_with_axes(data, column, f"Dotplot of {column}", "dot")
        else:
            plt.figure(figsize=(8, 6))
            sns.stripplot(x=data[column], jitter=True)
            plt.title(f"Dotplot of {column}")
            plt.xlabel(column)

        return self._save_plot(name)

    @register_tool
    @direct_send_message
    @cache_result
    async def plot_barplot(self, dataset: str, column: str) -> tuple[str, bytes]:
        """Generate a barplot for the specified dataset column."""
        duck_logger.debug(f"Generating barplot for {dataset}.{column}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "barplot")

        if column not in data.columns.to_list():
            column = await self._autocorrect(data.columns.to_list(), column)

        value_counts = data[column].value_counts()
        plt.figure(figsize=(8, 6))
        sns.barplot(x=value_counts.index, y=value_counts.values)
        plt.title(f"Barplot of {column}")
        plt.xlabel(column)
        plt.ylabel("Count")

        return self._save_plot(name)

    @register_tool
    @direct_send_message
    @cache_result
    async def plot_pie_chart(self, dataset: str, column: str) -> tuple[str, bytes]:
        """Generate a pie chart for the specified dataset column."""
        duck_logger.debug(f"Generating pie chart for {dataset}.{column}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "piechart")

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        if not self._is_categorical(data[column]):
            self._plot_message_with_axes(data, column, f"Pie Chart of {column}", "dot")
        else:
            value_counts = data[column].dropna().value_counts()
            labels = [f"{label} ({round(p * 100, 1)}%)" for label, p in (value_counts / value_counts.sum()).items()]
            plt.figure(figsize=(8, 6))
            plt.pie(value_counts.values, labels=labels, colors=sns.color_palette("pastel"), startangle=140,
                    autopct='%1.1f%%')
            plt.title(f"Pie Chart of {column}")
            plt.axis("equal")

        return self._save_plot(name)

    @register_tool
    @direct_send_message
    @cache_result
    async def plot_proportion_barplot(self, dataset: str, column: str) -> tuple[str, bytes]:
        """Generate a proportion barplot for the specified dataset column."""
        duck_logger.debug(f"Generating proportion barplot for {dataset}.{column}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        name = self._photo_name(dataset, column, "proportionbarplot")
        title = f"Proportion Barplot of {column}"

        # Let the enhanced plot message function handle fallback or actual plot
        self._plot_message_with_axes(data, column, title, kind="proportion")

        return self._save_plot(name)

    @register_tool
    async def calculate_mean(self, dataset: str, column: str) -> str:
        """Calculates the mean of a numeric column in the dataset, if not categorical."""
        duck_logger.debug(f"Calculating mean for: {column} in dataset: {dataset}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        series = data[column]
        if self._is_categorical(series):
            return "Mean cannot be calculated for categorical data"
        return f"Mean = {round(series.dropna().mean(), 4)}"

    @register_tool
    async def calculate_skewness(self, dataset: str, column: str) -> str:
        """Calculates the skewness (asymmetry) of a numeric column in the dataset."""
        duck_logger.debug(f"Calculating skewness for: {column} in dataset: {dataset}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        series = data[column]
        if self._is_categorical(series):
            return "Skewness cannot be calculated for categorical data"
        return f"Skewness = {round(skew(series.dropna()), 4)}"

    @register_tool
    async def calculate_std(self, dataset: str, column: str) -> str:
        """Calculates the standard deviation of a numeric column in the dataset."""
        duck_logger.debug(f"Calculating standard deviation for: {column} in dataset: {dataset}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        series = data[column]
        if self._is_categorical(series):
            return "Standard Deviation cannot be calculated for categorical data"
        return f"Standard Deviation = {round(series.dropna().std(), 4)}"

    @register_tool
    async def calculate_median(self, dataset: str, column: str) -> str:
        """Calculates the median (middle value) of a numeric column in the dataset."""
        duck_logger.debug(f"Calculating median for: {column} in dataset: {dataset}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        series = data[column]
        if self._is_categorical(series):
            return "Median cannot be calculated for categorical data"
        return f"Median = {round(series.dropna().median(), 4)}"

    @register_tool
    async def calculate_mode(self, dataset: str, column: str) -> str:
        """Estimates the mode of a numeric column using the peak of a KDE (kernel density estimate)."""
        duck_logger.debug(f"Calculating approximate mode (KDE) for: {column} in dataset: {dataset}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        series = data[column].dropna()

        if self._is_categorical(series):
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
    @direct_send_message
    async def calculate_five_number_summary(self, dataset: str, column: str) -> str:
        """Returns the five-number summary (min, Q1, median, Q3, max) for a numeric column in the dataset."""
        duck_logger.debug(f"Calculating five-number summary for: {column} in dataset: {dataset}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        series = data[column]
        if self._is_categorical(series):
            return "5 Number Summary cannot be calculated for categorical data"
        summary = series.dropna().quantile([0, 0.25, 0.5, 0.75, 1.0])
        labels = ["Min", "Q1", "Median", "Q3", "Max"]
        return "; ".join(f"{label}={round(val, 4)}" for label, val in zip(labels, summary))

    @register_tool
    async def calculate_table_of_counts(self, dataset: str, column: str) -> dict | str:
        """Returns a frequency table (category counts) for a categorical column in the dataset."""
        duck_logger.debug(f"Calculating table of counts for: {column} in dataset: {dataset}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        series = data[column]
        if not self._is_categorical(series):
            return "Table of Counts cannot be calculated for quantitative data"
        counts = series.value_counts(dropna=True).reset_index()
        counts.columns = ["Category", "Count"]
        return counts.to_dict(orient="records")

    @register_tool
    async def calculate_proportions(self, dataset: str, column: str) -> dict | str:
        """Returns the relative proportions of each category in a categorical column of the dataset."""
        duck_logger.debug(f"Calculating proportions for: {column} in dataset: {dataset}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column not in data.columns:
            column = await self._autocorrect(data.columns.to_list(), column)

        series = data[column]
        if not self._is_categorical(series):
            return "Proportions can only be calculated for categorical data"
        proportions = (series.value_counts(normalize=True, dropna=True).round(4).reset_index())
        proportions.columns = ["Category", "Proportion"]
        return proportions.to_dict(orient="records")

    # Tools for distribution statistics and visualizations

    @register_tool
    @direct_send_message
    def calculate_probability_from_normal_distribution(self, z1: float, z2 : Optional[float]=None, mean: float=0, std: float=1, tail: Literal["Upper Tail", "Lower Tail", "Between"] = "Lower Tail") -> str:
        """Calculates the probability for one or two z-scores from a normal distribution. Can handle upper tail, lower tail, or between two z-scores."""
        duck_logger.debug(f"Calculating probability for z1={z1}, z2={z2}, mean={mean}, std={std}, tail={tail}")
        z = (z1 - mean) / std
        if z2 is not None:
            z2 = (z2 - mean) / std

        if tail == "Upper Tail":
            return f"The probability is {round(norm.sf(z), 4)}"
        elif tail == "Lower Tail":
            return f"The probability is {round(norm.cdf(z), 4)}"
        elif tail == "Between" and z2 is not None:
            return f"The probability is {round(norm.cdf(max(z, z2)) - norm.cdf(min(z, z2)), 4)}"
        else:
            return "Invalid input for tail or missing z2"

    @register_tool
    @direct_send_message
    def calculate_percentiles_from_normal_distribution(self, p1: float, p2 : Optional[float]=None, mean: float=0, std: float=1, tail: Literal["Upper Tail", "Lower Tail", "Between"] = "Lower Tail") -> str:
        """Calculates z-score values corresponding to given percentiles from a normal distribution."""
        duck_logger.debug(f"Calculating percentiles for p1={p1}, p2={p2}, mean={mean}, std={std}, tail={tail}")
        p1 = p1 / 100 if p1 > 1 else p1
        if p2 is not None:
            p2 = p2 / 100 if p2 > 1 else p2

        if tail == "Upper Tail":
            return f"The percentile is {round(norm.ppf(1 - p1, loc=mean, scale=std), 4)}"
        elif tail == "Lower Tail":
            return f"The percentile is {round(norm.ppf(p1, loc=mean, scale=std), 4)}"
        elif tail == "Between" and p2 is not None:
            lower = norm.ppf(min(p1, p2), loc=mean, scale=std)
            upper = norm.ppf(max(p1, p2), loc=mean, scale=std)
            return f"The percentile is {round(lower, 4), round(upper, 4)}"
        else:
            return "Invalid input for tail or missing p2"

    @register_tool
    @direct_send_message
    @cache_result
    def plot_normal_distribution(self, z1: float, z2 : Optional[float]=None, mean: float=0, std: float=1, tail: Literal["Upper Tail", "Lower Tail", "Between"] = "Upper Tail") -> tuple[str, bytes]:
        """Plots a normal distribution with shaded areas for specified z-scores. If only one z-score is provided, it will shade the area for that z-score."""
        duck_logger.debug(f"Plotting normal distribution for z1={z1}, z2={z2}, mean={mean}, std={std}, tail={tail}")
        x = np.linspace(mean - 4 * std, mean + 4 * std, 1000)
        y = norm.pdf(x, mean, std)
        name = self._photo_name(z1, z2, mean, std, tail, "distribution")
        plt.figure(figsize=(10, 5))
        plt.plot(x, y, 'black')

        if tail == "Upper Tail":
            plt.fill_between(x, y, where=(x >= z1), color='blue', alpha=0.3)
        elif tail == "Lower Tail":
            plt.fill_between(x, y, where=(x <= z1), color='blue', alpha=0.3)
        elif tail == "Between" and z2 is not None:
            plt.fill_between(x, y, where=((x >= min(z1, z2)) & (x <= max(z1, z2))), color='blue', alpha=0.3)

        plt.title(f'Normal Distribution (mean={mean}, std={std})')
        plt.xlabel('Value')
        plt.ylabel('Density')
        plt.grid(True)
        return self._save_plot(name)


    @register_tool
    @direct_send_message
    async def calculate_confidence_interval_and_t_test(self, dataset: str, variable: str, alternative: Literal[
        "greater", "less", "two.sided"] = "two.sided", mu: float = 0, conf_level: float = 0.95) -> str:
        """Performs a one-sample t-test and returns a formatted summary string of the test results."""
        duck_logger.debug(
            f"Calculating confidence interval and t-test for {dataset}.{variable} with alternative={alternative}, mu={mu}, conf_level={conf_level}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)
        sample_data = data[variable].dropna()
        t_stat, p_value = ttest_1samp(sample_data, popmean=mu)
        df = len(sample_data) - 1
        mean_estimate = sample_data.mean()
        se = sample_data.std(ddof=1) / np.sqrt(len(sample_data))

        # Calculate confidence interval manually using t-critical value
        t_critical = stats.t.ppf((1 + conf_level) / 2, df)
        ci_lower = mean_estimate - t_critical * se
        ci_upper = mean_estimate + t_critical * se

        # Adjust p-value based on alternative hypothesis
        if alternative == "greater":
            p_value = p_value / 2 if t_stat > 0 else 1 - p_value / 2
        elif alternative == "less":
            p_value = p_value / 2 if t_stat < 0 else 1 - p_value / 2
        # For "two.sided", keep the original p_value

        summary = (
            f"t-Test for H0: Mean({variable}) = {mu}.\n"
            f"Alternative Hypothesis = {alternative}.\n"
            f"y-bar = {round(mean_estimate, 4)}.\n"
            f"t Test statistic = {round(t_stat, 4)}.\n"
            f"p-value = {round(p_value, 4)}.\n"
            f"{int(conf_level * 100)}% Confidence Interval: "
            f"({round(ci_lower, 4)}, {round(ci_upper, 4)}).\n"
        )
        return summary

    @register_tool
    @direct_send_message
    @cache_result
    async def plot_confidence_interval_and_t_distribution(self, dataset: str, column: str, alternative: Literal["greater", "less", "two.sided"] = "two.sided", mu: float= 0,
                                                    conf_level: float = 0.95) -> tuple[str, bytes] | str:
        """
        Plots the t-distribution with the test statistic and confidence interval.
        Returns a message and the image buffer of the plot.
        """
        duck_logger.debug(
            f"Plotting t-distribution for column={column} in dataset={dataset}, alternative={alternative}, mu={mu}, conf_level={conf_level}")

        name = self._photo_name(dataset, alternative, mu, conf_level, "t_distribution")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)
        series = data[column].dropna()

        if self._is_categorical(series):
            return "T-statistic cannot be calculated for categorical data"

        series_clean = series.dropna()
        n = len(series_clean)
        if n < 2:
            return "Not enough data to perform t-test"

        mean_estimate = series_clean.mean()
        std_err = np.std(series_clean, ddof=1) / np.sqrt(n)
        df = n - 1

        if std_err == 0:
            return "Standard error is zero, cannot perform t-test"

        t_stat = (mean_estimate - mu) / std_err

        try:
            conf_int = stats.t.interval(conf_level, df, loc=mean_estimate, scale=std_err)
        except Exception as e:
            duck_logger.error(f"Confidence interval calculation failed: {e}")
            return "Error calculating confidence interval"

        # Plotting
        x = np.linspace(stats.t.ppf(0.001, df), stats.t.ppf(0.999, df), 1000)
        y = stats.t.pdf(x, df)

        plt.figure(figsize=(10, 5))
        plt.plot(x, y, 'black', label='t-distribution')
        plt.axvline(t_stat, color='blue', linestyle='--', label=f't = {round(t_stat, 4)}')
        plt.xlabel('t')
        plt.ylabel('Density')
        plt.title('t-Distribution with Confidence Interval')

        # Shading rejection regions
        if alternative == "greater":
            plt.fill_between(x, y, where=(x >= stats.t.ppf(1 - (1 - conf_level), df)), color='red', alpha=0.3,
                             label='Rejection Region')
        elif alternative == "less":
            plt.fill_between(x, y, where=(x <= stats.t.ppf((1 - conf_level), df)), color='red', alpha=0.3,
                             label='Rejection Region')
        elif alternative == "two.sided":
            alpha = 1 - conf_level
            t_crit = stats.t.ppf(1 - alpha / 2, df)
            plt.fill_between(x, y, where=(x <= -t_crit), color='red', alpha=0.3, label='Rejection Region')
            plt.fill_between(x, y, where=(x >= t_crit), color='red', alpha=0.3)

        # Confidence Interval line
        plt.axvline((conf_int[0] - mu) / std_err, color='green', linestyle='--', label=f'{int(conf_level * 100)}% CI')
        plt.axvline((conf_int[1] - mu) / std_err, color='green', linestyle='--')
        plt.legend()
        plt.grid(True)

        return self._save_plot(name)

    # Tools for Two Mean EDA
    @register_tool
    @direct_send_message
    async def calculate_two_mean_t_test(self, dataset: str, column1: str, column2: str,
                                        alternative: Literal["greater", "less", "two.sided"] = "two.sided",
                                        conf_level: float = 0.95) -> str:
        """Performs a two-sample t-test on a numeric variable split by a categorical variable."""

        duck_logger.debug(f"Calculating two-sample t-test for {dataset}.{column1} and {dataset}.{column2}, "
                          f"alternative={alternative}, conf_level={conf_level}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if column1 not in data.columns:
            column1 = await self._autocorrect(data.columns.to_list(), column1)

        if column2 not in data.columns:
            column2 = await self._autocorrect(data.columns.to_list(), column2)

        # Identify categorical and numeric columns
        if self._is_categorical(data[column1]) and not self._is_categorical(data[column2]):
            group_col, value_col = column1, column2
        elif self._is_categorical(data[column2]) and not self._is_categorical(data[column1]):
            group_col, value_col = column2, column1
        else:
            return "Exactly one of the two columns must be categorical (with 2 levels) and the other numeric."

        # Drop missing values
        subset = data[[group_col, value_col]].dropna()

        # Get unique groups
        groups = subset[group_col].unique()
        if len(groups) != 2:
            return f"Categorical variable '{group_col}' must have exactly 2 levels for a two-sample t-test."

        # Extract the two samples
        group1_vals = subset[subset[group_col] == groups[0]][value_col]
        group2_vals = subset[subset[group_col] == groups[1]][value_col]

        if len(group1_vals) < 2 or len(group2_vals) < 2:
            return "Not enough data in one or both groups to perform the t-test."

        # Perform POOLED t-test (equal variances assumed)
        t_stat, p_value = stats.ttest_ind(group1_vals, group2_vals, equal_var=True)

        # Degrees of freedom for pooled t-test
        df = len(group1_vals) + len(group2_vals) - 2

        # Calculate pooled variance and standard error
        n1, n2 = len(group1_vals), len(group2_vals)
        var1, var2 = group1_vals.var(ddof=1), group2_vals.var(ddof=1)

        # Pooled variance
        pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / df

        # Standard error of difference in means
        se_diff = np.sqrt(pooled_var * (1 / n1 + 1 / n2))

        # Mean difference
        mean_diff = group1_vals.mean() - group2_vals.mean()

        # Confidence interval using pooled standard error
        t_critical = stats.t.ppf((1 + conf_level) / 2, df)
        ci_lower = mean_diff - t_critical * se_diff
        ci_upper = mean_diff + t_critical * se_diff

        # Adjust p-value based on alternative hypothesis
        if alternative == "greater":
            p_value = p_value / 2 if t_stat > 0 else 1 - p_value / 2
        elif alternative == "less":
            p_value = p_value / 2 if t_stat < 0 else 1 - p_value / 2
        # For "two.sided", keep the original p_value

        summary = (
            f"Two-Sample t-Test for H0: Mean({groups[0]}) = Mean({groups[1]}) on '{value_col}'.\n"
            f"Alternative Hypothesis: {alternative}.\n"
            f"Mean Difference = {round(mean_diff, 4)}.\n"
            f"t Test Statistic = {round(t_stat, 4)}.\n"
            f"p-value = {round(p_value, 4)}.\n"
            f"{int(conf_level * 100)}% Confidence Interval: "
            f"({round(ci_lower, 4)}, {round(ci_upper, 4)}).\n")

        return summary

    @register_tool
    @direct_send_message
    async def calculate_one_way_anova(self, dataset: str, group_column: str, value_column: str,
                                      conf_level: float = 0.95) -> str:
        """Performs a one-way ANOVA test on a numeric variable across groups defined by a categorical variable."""

        duck_logger.debug(
            f"Calculating one-way ANOVA for {dataset}.{value_column} grouped by {dataset}.{group_column}, "
            f"conf_level={conf_level}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if group_column not in data.columns:
            group_column = await self._autocorrect(data.columns.to_list(), group_column)

        if value_column not in data.columns:
            value_column = await self._autocorrect(data.columns.to_list(), value_column)

        # Validate variable types
        if not self._is_categorical(data[group_column]):
            return f"Group variable '{group_column}' must be categorical."

        if self._is_categorical(data[value_column]):
            return f"Value variable '{value_column}' must be numeric."

        # Drop missing values
        subset = data[[group_column, value_column]].dropna()

        # Get unique groups
        groups = subset[group_column].unique()
        n_groups = len(groups)

        if n_groups < 3:
            return f"Categorical variable '{group_column}' must have three or more groups for ANOVA. Found {n_groups} groups."

        # Check sample sizes
        group_counts = subset[group_column].value_counts()
        if any(group_counts < 2):
            return "Each group must have at least 2 observations to perform ANOVA."

        # Extract group data
        group_data = [subset[subset[group_column] == group][value_column].values for group in groups]

        # Perform one-way ANOVA
        f_stat, p_value = stats.f_oneway(*group_data)

        # Calculate degrees of freedom
        df_between = n_groups - 1
        df_within = len(subset) - n_groups
        df_total = len(subset) - 1

        # Calculate group statistics
        group_stats = []
        overall_mean = subset[value_column].mean()

        for group in groups:
            group_values = subset[subset[group_column] == group][value_column]
            group_stats.append({
                'group': group,
                'n': len(group_values),
                'mean': group_values.mean(),
                'std': group_values.std(ddof=1),
                'var': group_values.var(ddof=1)
            })

        # Calculate confidence intervals for group means
        # Using pooled standard error (MSE from ANOVA)
        ss_within = sum([(stat['n'] - 1) * stat['var'] for stat in group_stats])
        mse = ss_within / df_within

        confidence_intervals = []
        t_critical = stats.t.ppf((1 + conf_level) / 2, df_within)

        for stat in group_stats:
            se = np.sqrt(mse / stat['n'])
            ci_lower = stat['mean'] - t_critical * se
            ci_upper = stat['mean'] + t_critical * se
            confidence_intervals.append({
                'group': stat['group'],
                'mean': stat['mean'],
                'ci_lower': ci_lower,
                'ci_upper': ci_upper
            })

        # Format results
        summary = (
            f"One-Way ANOVA Test for H0: All group means are equal on '{value_column}'.\n"
            f"Groups defined by: '{group_column}' ({n_groups} groups).\n"
            f"F-statistic = {round(f_stat, 4)}.\n"
            f"p-value = {round(p_value, 4)}.\n"
            f"Degrees of freedom: Between groups = {df_between}, Within groups = {df_within}.\n\n"
            f"Group Statistics:\n"
        )

        for stat in group_stats:
            summary += (f"  {stat['group']}: n = {stat['n']}, "
                        f"mean = {round(stat['mean'], 4)}, "
                        f"sd = {round(stat['std'], 4)}\n")

        summary += f"\n{int(conf_level * 100)}% Confidence Intervals for Group Means:\n"
        for ci in confidence_intervals:
            summary += (f"  {ci['group']}: ({round(ci['ci_lower'], 4)}, "
                        f"{round(ci['ci_upper'], 4)})\n")

        return summary


    @register_tool
    @direct_send_message
    async def calculate_one_sample_proportion_z_test(self, dataset: str, variable: str, category: str,
                                                     p_null: float = 0.5,
                                                     alternative: Literal["greater", "less", "two.sided"] = "two.sided",
                                                     conf_level: float = 0.95) -> str:
        """
        Performs a one-sample z-test for proportions, testing whether the proportion of a category equals p_null.
        """

        duck_logger.debug(
            f"Z-test for dataset={dataset}, variable={variable}, category={category}, p_null={p_null}, alternative={alternative}, conf_level={conf_level}")

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        if variable not in data.columns:
            variable = await self._autocorrect(data.columns.to_list(), variable)

        if category not in data[variable].unique():
            category = await self._autocorrect(data[variable].unique(), category)

        series = data[variable].dropna()

        if not self._is_categorical(series):
            return f"The variable '{variable}' must be categorical for a proportion z-test."

        n = len(series)
        if n == 0:
            return "The selected variable contains no non-missing values."

        phat = np.sum(series == category) / n

        se = np.sqrt(p_null * (1 - p_null) / n)
        z_stat = (phat - p_null) / se

        if alternative == "greater":
            p_value = 1 - norm.cdf(z_stat)
        elif alternative == "less":
            p_value = norm.cdf(z_stat)
        else:  # "two.sided"
            p_value = 2 * min(norm.cdf(z_stat), 1 - norm.cdf(z_stat))

        se_phat = np.sqrt(phat * (1 - phat) / n)
        z_critical = norm.ppf(1 - (1 - conf_level) / 2)
        ci_lower = phat - z_critical * se_phat
        ci_upper = phat + z_critical * se_phat

        summary = (
            f"Z-Test for H0: π({category}) = {p_null}\n"
            f"Alternative Hypothesis: π({category}) {alternative.replace('two.sided', '≠')} {p_null}\n"
            f"Observed proportion (p̂): {round(phat, 4)}\n"
            f"Z Test Statistic: {round(z_stat, 4)}\n"
            f"P-value: {round(p_value, 4)}\n"
            f"Sample size (n): {n}\n"
            f"{int(conf_level * 100)}% Confidence Interval for π({category}): "
            f"({round(ci_lower, 4)}, {round(ci_upper, 4)})"
        )
        return summary


    @register_tool
    @direct_send_message
    async def calculate_two_sample_proportion_z_test(self, dataset: str, response_variable: str, response_category: str,
                                                     group_variable: str, group1: str, group2: str,
                                                     alternative: Literal["greater", "less", "two.sided"] = "two.sided",
                                                     conf_level: float = 0.95) -> str:
        """
        Performs a two-sample z-test for proportions, testing whether the proportion of response_category is the same in two groups.
        """
        duck_logger.debug(
            f"Two-sample Z-test on dataset={dataset}, response_variable={response_variable}, "
            f"response_category={response_category}, group_variable={group_variable}, group1={group1}, group2={group2}, "
            f"alternative={alternative}, conf_level={conf_level}"
        )

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        # Autocorrect any variable names
        for var in [response_variable, group_variable]:
            if var not in data.columns:
                corrected = await self._autocorrect(data.columns.to_list(), var)
                if var == response_variable:
                    response_variable = corrected
                else:
                    group_variable = corrected

        if response_category not in data[response_variable].unique():
            response_category = await self._autocorrect(data[response_variable].unique(), response_category)

        for group_val in [group1, group2]:
            if group_val not in data[group_variable].unique():
                corrected = await self._autocorrect(data[group_variable].unique(), group_val)
                if group_val == group1:
                    group1 = corrected
                else:
                    group2 = corrected

        # Filter out missing values
        df = data[[response_variable, group_variable]].dropna()
        if not self._is_categorical(df[response_variable]) or not self._is_categorical(df[group_variable]):
            return f"Both '{response_variable}' and '{group_variable}' must be categorical for a two-sample proportion z-test."

        # Group counts
        group1_data = df[df[group_variable] == group1]
        group2_data = df[df[group_variable] == group2]

        n1 = len(group1_data)
        n2 = len(group2_data)

        if n1 == 0 or n2 == 0:
            return f"One or both groups have no observations."

        phat1 = np.sum(group1_data[response_variable] == response_category) / n1
        phat2 = np.sum(group2_data[response_variable] == response_category) / n2

        pooled_phat = (phat1 * n1 + phat2 * n2) / (n1 + n2)
        se = np.sqrt(pooled_phat * (1 - pooled_phat) * (1 / n1 + 1 / n2))

        z_stat = (phat1 - phat2) / se

        # Compute p-value
        if alternative == "greater":
            p_value = 1 - norm.cdf(z_stat)
        elif alternative == "less":
            p_value = norm.cdf(z_stat)
        else:  # "two.sided"
            p_value = 2 * min(norm.cdf(z_stat), 1 - norm.cdf(z_stat))

        # Confidence interval for difference in proportions
        se_diff = np.sqrt(phat1 * (1 - phat1) / n1 + phat2 * (1 - phat2) / n2)
        z_critical = norm.ppf(1 - (1 - conf_level) / 2)
        ci_lower = (phat1 - phat2) - z_critical * se_diff
        ci_upper = (phat1 - phat2) + z_critical * se_diff

        summary = (
            f"Two-Sample Z-Test for H0: π({group1}) = π({group2})\n"
            f"Alternative Hypothesis: π({group1}) {alternative.replace('two.sided', '≠')} π({group2})\n"
            f"phat({group1}) = {round(phat1, 4)}\n"
            f"phat({group2}) = {round(phat2, 4)}\n"
            f"Difference (phat1 - phat2) = {round(phat1 - phat2, 4)}\n"
            f"Z Test Statistic: {round(z_stat, 4)}\n"
            f"P-value: {round(p_value, 4)}\n"
            f"{int(conf_level * 100)}% Confidence Interval for Difference: "
            f"({round(ci_lower, 4)}, {round(ci_upper, 4)})"
        )

        return summary


    @register_tool
    @direct_send_message
    async def calculate_chi_squared_test(self, dataset: str, row_variable: str, col_variable: str) -> str:
        """
        Performs a Chi-squared test of independence between two categorical variables.
        """
        duck_logger.debug(
            f"Chi-squared test on dataset={dataset}, row_variable={row_variable}, col_variable={col_variable}"
        )

        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)

        data = self._datastore.get_dataset(dataset)

        # Autocorrect variable names
        for var in [row_variable, col_variable]:
            if var not in data.columns:
                corrected = await self._autocorrect(data.columns.to_list(), var)
                if var == row_variable:
                    row_variable = corrected
                else:
                    col_variable = corrected

        df = data[[row_variable, col_variable]].dropna()

        if not self._is_categorical(df[row_variable]) or not self._is_categorical(df[col_variable]):
            return f"Both '{row_variable}' and '{col_variable}' must be categorical for a Chi-squared test."

        contingency_table = pd.crosstab(df[row_variable], df[col_variable])

        if contingency_table.empty:
            return "The contingency table is empty after removing missing values. Please check your inputs."

        chi2, p, dof, expected = chi2_contingency(contingency_table)

        summary = (
            f"Chi-squared Test of Independence\n"
            f"Variables: {row_variable} and {col_variable}\n"
            f"Degrees of Freedom: {dof}\n"
            f"Test Statistic (χ²): {round(chi2, 4)}\n"
            f"P-value: {round(p, 4)}\n\n"
            f"Observed Table:\n{contingency_table.to_string()}\n\n"
            f"Expected Counts:\n{pd.DataFrame(expected, index=contingency_table.index, columns=contingency_table.columns).round(2).to_string()}"
        )

        return summary


    @register_tool
    @direct_send_message
    async def simple_linear_regression(
        self,
        dataset: str,
        response: str,
        explanatory: str,
        prediction_value: float = None,
        interval_type: Literal["confidence", "prediction"] = "confidence",
        conf_level: float = 0.95,
        cv_folds: int = 5
    ) -> str:
        """Performs simple linear regression with summary statistics, confidence intervals, prediction, and cross-validation."""

        duck_logger.debug(
            f"Running SLR on {dataset}: {response} ~ {explanatory}, prediction_value={prediction_value}, "
            f"interval_type={interval_type}, conf_level={conf_level}, cv_folds={cv_folds}"
        )

        # Load dataset
        if dataset not in self._datastore.get_available_datasets():
            dataset = await self._autocorrect(self._datastore.get_available_datasets(), dataset)
        data = self._datastore.get_dataset(dataset)

        # Validate column names
        if response not in data.columns:
            response = await self._autocorrect(data.columns.tolist(), response)
        if explanatory not in data.columns:
            explanatory = await self._autocorrect(data.columns.tolist(), explanatory)

        df = data[[response, explanatory]].dropna()
        if df.empty:
            return "No valid data after removing missing values."

        # Ensure response is numeric
        if not pd.api.types.is_numeric_dtype(df[response]):
            try:
                df[response] = pd.to_numeric(df[response], errors="coerce")
                df = df.dropna(subset=[response])
            except Exception:
                return f"The response variable '{response}' could not be converted to numeric."

        if df.empty:
            return "No valid rows remain after cleaning non-numeric or missing values."

        # Handle categorical or numeric explanatory variable
        if self._is_categorical(df[explanatory]):
            df[explanatory] = df[explanatory].astype("category")
            formula = f"{response} ~ C({explanatory})"
        else:
            formula = f"{response} ~ {explanatory}"

        # Fit regression model
        try:
            model = smf.ols(formula=formula, data=df).fit()
        except Exception as e:
            return f"Failed to fit regression model: {str(e)}"

        # Coefficients + CI
        coef_summary = model.summary2().tables[1]
        conf_ints = model.conf_int(alpha=1 - conf_level)
        coef_summary["CI Lower Bound"] = conf_ints[0]
        coef_summary["CI Upper Bound"] = conf_ints[1]

        coef_summary = coef_summary[["Coef.", "t", "P>|t|", "CI Lower Bound", "CI Upper Bound"]]
        coef_summary.columns = ["Estimate", "t value", "p-value", "CI Lower Bound", "CI Upper Bound"]

        # Optional prediction
        prediction_output = ""
        if prediction_value is not None:
            try:
                new_data = pd.DataFrame({explanatory: [prediction_value]})
                pred = model.get_prediction(new_data)
                pred_summary = pred.summary_frame(alpha=1 - conf_level)
                prediction = pred_summary.iloc[0]
                prediction_output = (
                    f"\nPrediction for {response} when {explanatory} = {prediction_value}:\n"
                    f"Predicted value: {round(prediction['mean'], 4)}\n"
                    f"{int(conf_level * 100)}% {interval_type.title()} Interval: "
                    f"({round(prediction[f'{interval_type}_ci_lower'], 4)}, "
                    f"{round(prediction[f'{interval_type}_ci_upper'], 4)})\n"
                )
            except Exception as e:
                prediction_output = f"\nPrediction could not be generated: {e}"

        # Cross-validated RMSE
        kf = KFold(n_splits=cv_folds, shuffle=True, random_state=1)
        rmse_scores = []

        for train_idx, test_idx in kf.split(df):
            train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]
            cv_model = smf.ols(formula=formula, data=train_df).fit()
            preds = cv_model.predict(test_df)
            rmse = np.sqrt(mean_squared_error(test_df[response], preds))
            rmse_scores.append(rmse)

        mean_rmse = round(np.mean(rmse_scores), 4)

        # Final output
        return (
            f"Simple Linear Regression: {response} ~ {explanatory}\n"
            f"R-squared: {round(model.rsquared, 4)}\n"
            f"Residual standard error (sigma): {round(np.sqrt(model.scale), 4)}\n"
            f"\nCoefficient Summary:\n{coef_summary.to_string()}\n"
            f"\nCross-validated RMSE ({cv_folds}-fold): {mean_rmse}\n"
            f"{prediction_output}"
        )
