import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from scipy.stats import skew, norm, ttest_1samp, t
from seaborn.external.kde import gaussian_kde

from .cache import Cache, cache_tool, BytesIOPrep
from .tools import register_tool
from ..utils.data_store import DataStore
from ..utils.logger import duck_logger


class StatsTools:
    def __init__(self, datastore: DataStore, cache: Cache):
        self._datastore = datastore
        self._cache = cache

    def _is_categorical(self, series) -> bool:
        if isinstance(series, list) or isinstance(series, dict):
            series = pd.Series(series)
        if not isinstance(series, pd.Series):
            raise ValueError(f"Expected a pandas Series, got {type(series)}")
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
            if values.empty:
                raise ValueError(f"No valid numeric data found in column '{column}' for plotting.")
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

    def _save_plot(self, name: str) -> tuple[str, io.BytesIO]:
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        plt.close()
        return name, buffer

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
    def get_variable_names(self, dataset: str) -> str:
        """Returns a list of all variable names in the dataset."""
        duck_logger.debug(f"Used get_variable_names on dataset={dataset}")
        data = self._datastore.get_dataset(dataset).columns.to_list()
        return f"Variable names in {dataset}: {', '.join(data)}"

    @register_tool
    @cache_tool(BytesIOPrep())
    def show_dataset_head(self, dataset: str, n: int) -> tuple[str, io.BytesIO]:
        """Shows the first n rows of the dataset as a table image."""
        duck_logger.debug(f"Generating head preview for {dataset} with n={n}")
        data = self._datastore.get_dataset(dataset)

        if not isinstance(n, int) or n <= 0:
            raise ValueError("n must be a positive integer.")

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

        return name, buf

    # Tools for dataset statistics and visualizations
    @register_tool
    @cache_tool(BytesIOPrep())
    def plot_histogram(self, dataset: str, column: str) -> tuple[str, io.BytesIO]:
        """Generate a histogram for the specified dataset column."""
        duck_logger.debug(f"Generating histogram plot for {dataset}.{column}")
        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "histogram")

        if column not in data.columns.to_list():
            raise ValueError(f"Column '{column}' not found in dataset.")

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
    @cache_tool(BytesIOPrep())
    def plot_boxplot(self, dataset: str, column: str) -> tuple[str, io.BytesIO]:
        """Generate a boxplot for the specified dataset column."""
        duck_logger.debug(f"Generating boxplot for {dataset}.{column}")
        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "boxplot")

        if column not in data.columns.to_list():
            raise ValueError(f"Column '{column}' not found.")

        if self._is_categorical(data[column]):
            self._plot_message_with_axes(data, column, f"Boxplot of {column}", "box")
        else:
            plt.figure(figsize=(8, 6))
            sns.boxplot(y=data[column])
            plt.title(f"Boxplot of {column}")
            plt.ylabel(column)

        return self._save_plot(name)

    @register_tool
    @cache_tool(BytesIOPrep())
    def plot_dotplot(self, dataset: str, column: str) -> tuple[str, io.BytesIO]:
        """Generate a dotplot for the specified dataset column."""
        duck_logger.debug(f"Generating dotplot for {dataset}.{column}")
        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "dotplot")

        if column not in data.columns.to_list():
            raise ValueError(f"Column '{column}' not found.")

        if self._is_categorical(data[column]):
            self._plot_message_with_axes(data, column, f"Dotplot of {column}", "dot")
        else:
            plt.figure(figsize=(8, 6))
            sns.stripplot(x=data[column], jitter=True)
            plt.title(f"Dotplot of {column}")
            plt.xlabel(column)

        return self._save_plot(name)

    @register_tool
    @cache_tool(BytesIOPrep())
    def plot_barplot(self, dataset: str, column: str) -> tuple[str, io.BytesIO]:
        """Generate a barplot for the specified dataset column."""
        duck_logger.debug(f"Generating barplot for {dataset}.{column}")
        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "barplot")

        if column not in data.columns.to_list():
            raise ValueError(f"Column '{column}' not found.")

        value_counts = data[column].value_counts()
        plt.figure(figsize=(8, 6))
        sns.barplot(x=value_counts.index, y=value_counts.values)
        plt.title(f"Barplot of {column}")
        plt.xlabel(column)
        plt.ylabel("Count")

        return self._save_plot(name)

    @register_tool
    @cache_tool(BytesIOPrep())
    def plot_pie_chart(self, dataset: str, column: str) -> tuple[str, io.BytesIO]:
        """Generate a pie chart for the specified dataset column."""
        duck_logger.debug(f"Generating pie chart for {dataset}.{column}")
        data = self._datastore.get_dataset(dataset)
        name = self._photo_name(dataset, column, "piechart")

        if column not in data.columns:
            raise ValueError(f"Column '{column}' not found.")

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
    @cache_tool(BytesIOPrep())
    def plot_proportion_barplot(self, dataset: str, column: str) -> tuple[str, io.BytesIO]:
        """Generate a proportion barplot for the specified dataset column."""
        duck_logger.debug(f"Generating proportion barplot for {dataset}.{column}")
        data = self._datastore.get_dataset(dataset)

        name = self._photo_name(dataset, column, "proportionbarplot")
        title = f"Proportion Barplot of {column}"

        # Let the enhanced plot message function handle fallback or actual plot
        self._plot_message_with_axes(data, column, title, kind="proportion")

        return self._save_plot(name)

    @register_tool
    def calculate_mean(self, dataset: str, column: str) -> str:
        """Calculates the mean of a numeric column in the dataset, if not categorical."""
        duck_logger.debug(f"Calculating mean for: {column} in dataset: {dataset}")
        data = self._datastore.get_dataset(dataset)
        series = data[column]
        if self._is_categorical(series):
            return "Mean cannot be calculated for categorical data"
        return f"Mean = {round(series.dropna().mean(), 4)}"

    @register_tool
    def calculate_skewness(self, dataset: str, column: str) -> str:
        """Calculates the skewness (asymmetry) of a numeric column in the dataset."""
        duck_logger.debug(f"Calculating skewness for: {column} in dataset: {dataset}")
        data = self._datastore.get_dataset(dataset)
        series = data[column]
        if self._is_categorical(series):
            return "Skewness cannot be calculated for categorical data"
        return f"Skewness = {round(skew(series.dropna()), 4)}"

    @register_tool
    def calculate_std(self, dataset: str, column: str) -> str:
        """Calculates the standard deviation of a numeric column in the dataset."""
        duck_logger.debug(f"Calculating standard deviation for: {column} in dataset: {dataset}")
        data = self._datastore.get_dataset(dataset)
        series = data[column]
        if self._is_categorical(series):
            return "Standard Deviation cannot be calculated for categorical data"
        return f"Standard Deviation = {round(series.dropna().std(), 4)}"

    @register_tool
    def calculate_median(self, dataset: str, column: str) -> str:
        """Calculates the median (middle value) of a numeric column in the dataset."""
        duck_logger.debug(f"Calculating median for: {column} in dataset: {dataset}")
        data = self._datastore.get_dataset(dataset)
        series = data[column]
        if self._is_categorical(series):
            return "Median cannot be calculated for categorical data"
        return f"Median = {round(series.dropna().median(), 4)}"

    @register_tool
    def calculate_mode(self, dataset: str, column: str) -> str:
        """Estimates the mode of a numeric column using the peak of a KDE (kernel density estimate)."""
        duck_logger.debug(f"Calculating approximate mode (KDE) for: {column} in dataset: {dataset}")
        data = self._datastore.get_dataset(dataset)
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
    def calculate_five_number_summary(self, dataset: str, column: str) -> str:
        """Returns the five-number summary (min, Q1, median, Q3, max) for a numeric column in the dataset."""
        duck_logger.debug(f"Calculating five-number summary for: {column} in dataset: {dataset}")
        data = self._datastore.get_dataset(dataset)
        series = data[column]
        if self._is_categorical(series):
            return "5 Number Summary cannot be calculated for categorical data"
        summary = series.dropna().quantile([0, 0.25, 0.5, 0.75, 1.0])
        labels = ["Min", "Q1", "Median", "Q3", "Max"]
        return "; ".join(f"{label}={round(val, 4)}" for label, val in zip(labels, summary))

    @register_tool
    def calculate_table_of_counts(self, dataset: str, column: str) -> dict | str:
        """Returns a frequency table (category counts) for a categorical column in the dataset."""
        duck_logger.debug(f"Calculating table of counts for: {column} in dataset: {dataset}")
        data = self._datastore.get_dataset(dataset)
        series = data[column]
        if not self._is_categorical(series):
            return "Table of Counts cannot be calculated for quantitative data"
        counts = series.value_counts(dropna=True).reset_index()
        counts.columns = ["Category", "Count"]
        return counts.to_dict(orient="records")

    @register_tool
    def calculate_proportions(self, dataset: str, column: str) -> dict | str:
        """Returns the relative proportions of each category in a categorical column of the dataset."""
        duck_logger.debug(f"Calculating proportions for: {column} in dataset: {dataset}")
        data = self._datastore.get_dataset(dataset)
        series = data[column]
        if not self._is_categorical(series):
            return "Proportions can only be calculated for categorical data"
        proportions = (series.value_counts(normalize=True, dropna=True).round(4).reset_index())
        proportions.columns = ["Category", "Proportion"]
        return proportions.to_dict(orient="records")

    # Tools for distribution statistics and visualizations

    @register_tool
    def calculate_probability_from_normal_distribution(self, z1, z2=None, mean=0, std=1, tail="Upper Tail"):
        """Calculates the probability for one or two z-scores from a normal distribution."""
        duck_logger.debug(f"Calculating probability for z1={z1}, z2={z2}, mean={mean}, std={std}, tail={tail}")
        z = (z1 - mean) / std
        if z2 is not None:
            z2 = (z2 - mean) / std

        if tail == "Upper Tail":
            return round(norm.sf(z), 4)
        elif tail == "Lower Tail":
            return round(norm.cdf(z), 4)
        elif tail == "Between" and z2 is not None:
            return round(norm.cdf(max(z, z2)) - norm.cdf(min(z, z2)), 4)
        else:
            raise ValueError("Invalid input for tail or missing z2")

    @register_tool
    def calculate_percentiles_from_normal_distribution(self, p1, p2=None, mean=0, std=1, tail="Lower Tail"):
        """Calculates z-score values corresponding to given percentiles from a normal distribution."""
        duck_logger.debug(f"Calculating percentiles for p1={p1}, p2={p2}, mean={mean}, std={std}, tail={tail}")
        p1 = p1 / 100 if p1 > 1 else p1
        if p2 is not None:
            p2 = p2 / 100 if p2 > 1 else p2

        if tail == "Upper Tail":
            return round(norm.ppf(1 - p1, loc=mean, scale=std), 4)
        elif tail == "Lower Tail":
            return round(norm.ppf(p1, loc=mean, scale=std), 4)
        elif tail == "Between" and p2 is not None:
            lower = norm.ppf(min(p1, p2), loc=mean, scale=std)
            upper = norm.ppf(max(p1, p2), loc=mean, scale=std)
            return round(lower, 4), round(upper, 4)
        else:
            raise ValueError("Invalid input for tail or missing p2")

    @register_tool
    @cache_tool(BytesIOPrep())
    def plot_normal_distribution(self, z1, z2=None, mean=0, std=1, tail="Upper Tail") -> tuple[str, io.BytesIO]:
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

    # Tools for Single Mean EDA

    @register_tool
    def calculate_confidence_interval_and_t_test(self, dataset, variable, alternative="two.sided", mu=0, conf_level=0.95) -> str:
        """Performs a one-sample t-test and returns a formatted summary string of the test results."""
        duck_logger.debug(f"Calculating confidence interval and t-test for {dataset}.{variable} with alternative={alternative}, mu={mu}, conf_level={conf_level}")
        data = self._datastore.get_dataset(dataset)
        sample_data = data[variable].dropna()
        t_stat, p_value = ttest_1samp(sample_data, popmean=mu)
        df = len(sample_data) - 1
        mean_estimate = sample_data.mean()
        se = sample_data.std(ddof=1) / np.sqrt(len(sample_data))
        ci_range = t.interval(conf_level, df, loc=mean_estimate, scale=se)

        if alternative == "greater":
            p_value = p_value / 2 if t_stat > 0 else 1 - p_value / 2
        elif alternative == "less":
            p_value = p_value / 2 if t_stat < 0 else 1 - p_value / 2

        summary = (
            f"t-Test for H0: Mean({variable}) = {mu}.\n"
            f"Alternative Hypothesis = {alternative}.\n"
            f"y-bar = {round(mean_estimate, 4)}.\n"
            f"t Test statistic = {round(t_stat, 4)}.\n"
            f"p-value = {round(p_value, 4)}.\n"
            f"{int(conf_level * 100)}% Confidence Interval: "
            f"{tuple(round(x, 4) for x in ci_range)}.\n"
        )
        return summary

    @register_tool
    @cache_tool(BytesIOPrep())
    def plot_confidence_interval_and_t_distribution(self, dataset: str, column: str, alternative="two.sided", mu=0,
                                                    conf_level=0.95) -> tuple[str, io.BytesIO]:
        """
        Plots the t-distribution with the test statistic and confidence interval.
        Returns a message and the image buffer of the plot.
        """
        duck_logger.debug(
            f"Plotting t-distribution for column={column} in dataset={dataset}, alternative={alternative}, mu={mu}, conf_level={conf_level}")

        name = self._photo_name(dataset, alternative, mu, conf_level, "t_distribution")
        data = self._datastore.get_dataset(dataset)
        series = data[column].dropna()

        if self._is_categorical(series):
            return ("T-statistic cannot be calculated for categorical data", io.BytesIO())

        series_clean = series.dropna()
        n = len(series_clean)
        if n < 2:
            return ("Not enough data to perform t-test", io.BytesIO())

        mean_estimate = series_clean.mean()
        std_err = np.std(series_clean, ddof=1) / np.sqrt(n)
        df = n - 1

        if std_err == 0:
            return ("Standard error is zero, cannot perform t-test", io.BytesIO())

        t_stat = (mean_estimate - mu) / std_err

        try:
            conf_int = stats.t.interval(conf_level, df, loc=mean_estimate, scale=std_err)
        except Exception as e:
            duck_logger.error(f"Confidence interval calculation failed: {e}")
            return ("Error calculating confidence interval", io.BytesIO())

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
    def calculate_two_mean_t_test(self, dataset: str, column1: str, column2: str, alternative="two.sided",
                                   conf_level=0.95) -> str:
        """Performs a two-sample t-test on a numeric variable split by a categorical variable."""

        duck_logger.debug(f"Calculating two-sample t-test for {dataset}.{column1} and {dataset}.{column2}, "
                          f"alternative={alternative}, conf_level={conf_level}")

        data = self._datastore.get_dataset(dataset)

        # Identify categorical and numeric columns
        if self._is_categorical(column1) and not self._is_categorical(column2):
            group_col, value_col = column1, column2
        elif self._is_categorical(column2) and not self._is_categorical(column1):
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

        # Perform t-test
        t_stat, p_value = stats.ttest_ind(group1_vals, group2_vals, equal_var=False)

        # Degrees of freedom
        df = len(group1_vals) + len(group2_vals) - 2

        # Mean difference and CI
        mean_diff = group1_vals.mean() - group2_vals.mean()
        se_diff = np.sqrt(group1_vals.var(ddof=1) / len(group1_vals) +
                          group2_vals.var(ddof=1) / len(group2_vals))
        ci_range = stats.t.interval(conf_level, df, loc=mean_diff, scale=se_diff)

        # Adjust p-value based on one-sided test
        if alternative == "greater":
            p_value = p_value / 2 if t_stat > 0 else 1 - p_value / 2
        elif alternative == "less":
            p_value = p_value / 2 if t_stat < 0 else 1 - p_value / 2

        summary = (
            f"Two-Sample t-Test for H0: Mean({groups[0]}) = Mean({groups[1]}) on '{value_col}'.\n"
            f"Alternative Hypothesis: {alternative}.\n"
            f"Mean Difference = {round(mean_diff, 4)}.\n"
            f"t Test Statistic = {round(t_stat, 4)}.\n"
            f"p-value = {round(p_value, 4)}.\n"
            f"{int(conf_level * 100)}% Confidence Interval: "
            f"{tuple(round(x, 4) for x in ci_range)}.\n"
        )
        return summary