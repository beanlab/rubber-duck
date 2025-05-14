# Available Tools

### `get_variable_names`
**Signature**: `get_variable_names(dataset: str) -> list[str]`

Returns the variable names (columns) of the dataset.

### `get_column_data`
**Signature**: `get_column_data(dataset: str, column: str) -> pandas.core.series.Series`

Returns the data of a specific column in the dataset.

### `plot_histogram`
**Signature**: `plot_histogram(dataset: str, column: str) -> pathlib.Path`

Generates a histogram with KDE for the specified numeric column in a dataset, or a message image if the column is categorical.

### `plot_boxplot`
**Signature**: `plot_boxplot(dataset: str, column: str) -> pathlib.Path`

Creates a boxplot of the specified numeric column in a dataset, or a message image if the column is categorical.

### `plot_dotplot`
**Signature**: `plot_dotplot(dataset: str, column: str) -> pathlib.Path`

Creates a dot plot (strip plot) for the specified numeric column, or a message image if the column is categorical.

### `plot_barplot`
**Signature**: `plot_barplot(dataset: str, column: str) -> pathlib.Path`

Creates a bar plot of value counts for a categorical column in the dataset.

### `plot_pie_chart`
**Signature**: `plot_pie_chart(dataset: str, column: str) -> pathlib.Path`

Creates a pie chart of value proportions for a categorical column, or a message image if the column is numeric.

### `calculate_mean`
**Signature**: `calculate_mean(dataset: str, column: str) -> str`

Calculates the mean of a numeric column in the dataset, if not categorical.

### `calculate_skewness`
**Signature**: `calculate_skewness(dataset: str, column: str) -> str`

Calculates the skewness (asymmetry) of a numeric column in the dataset.

### `calculate_std`
**Signature**: `calculate_std(dataset: str, column: str) -> str`

Calculates the standard deviation of a numeric column in the dataset.

### `calculate_median`
**Signature**: `calculate_median(dataset: str, column: str) -> str`

Calculates the median (middle value) of a numeric column in the dataset.

### `calculate_mode`
**Signature**: `calculate_mode(dataset: str, column: str) -> str`

Estimates the mode of a numeric column using the peak of a KDE (kernel density estimate).

### `calculate_five_number_summary`
**Signature**: `calculate_five_number_summary(dataset: str, column: str) -> str`

Returns the five-number summary (min, Q1, median, Q3, max) for a numeric column in the dataset.

### `calculate_table_of_counts`
**Signature**: `calculate_table_of_counts(dataset: str, column: str) -> dict | str`

Returns a frequency table (category counts) for a categorical column in the dataset.

### `calculate_proportions`
**Signature**: `calculate_proportions(dataset: str, column: str) -> dict | str`

Returns the relative proportions of each category in a categorical column of the dataset.

