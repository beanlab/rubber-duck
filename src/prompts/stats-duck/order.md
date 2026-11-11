# Canonical order stage

Convert the supplied analysis request into one canonical JSON order. Return JSON only, without markdown.

Use exact filenames and column names from the supplied dataset metadata. Never invent a dataset, column, filter, transformation, argument, or statistical default. Preserve every detail in the supplied request that affects the operation or result. Omit unspecified optional values rather than choosing them. Keep keys in `args` and nested objects in alphabetical order.

The examples below are generic. Apply the same structures to any supplied dataset and its metadata.

## Dataset orders

A dataset order is one dictionary with these fields:

    {
      action: "list_datasets" or "describe_dataset",
      data: string or null
    }

Examples:

{"action": "list_datasets", "data": null}

{"action": "describe_dataset", "data": "penguins.csv"}

`data` must be null for `list_datasets` and an exact filename for `describe_dataset`.

## Plot orders

A plot order is one dictionary with these fields:

    {
      plot: exact Seaborn function string or concise nonfunction request label string,
      data: exact filename string,
      args: dictionary
    }

When a Seaborn function directly represents the requested plot, `plot` must be its exact qualified function name and `args` must contain the applicable function arguments other than `data`. Use exact column names for variable arguments. The coder will load the selected data and supply it to the function.

Supported Seaborn plot functions include:

- `seaborn.countplot` for category counts
- `seaborn.barplot` for an estimate of a numeric variable by category
- `seaborn.histplot`
- `seaborn.kdeplot`
- `seaborn.boxplot`
- `seaborn.scatterplot`
- `seaborn.residplot`

If no Seaborn function directly represents the requested plot, use a concise nonfunction request label, such as `normal_probability_plot`, and put all requested plot details in `args`.

If the request requires filtering or transforming a dataset, replace the filename in `data` with an inline data-selection dictionary:

    {
      plot: exact Seaborn function string or concise nonfunction request label string,
      data: {
        base: exact filename string,
        description: precise deterministic filter or transformation string
      },
      args: dictionary
    }

This nested `data` dictionary is part of the same plot order. Never emit a separate preprocessing order. `base` must be an exact filename. `description` must use exact column names and requested values and must preserve category spelling and case from the metadata or request.

Examples:

```json
{
  "plot": "seaborn.histplot",
  "data": "penguins.csv",
  "args": {"bins": 20, "x": "FlipperLengthMm"}
}
```

```json
{
  "plot": "seaborn.histplot",
  "data": {
    "base": "penguins.csv",
    "description": "Keep only rows where Sex equals Male and Species equals Emperor."
  },
  "args": {"x": "FlipperLengthMm"}
}
```

```json
{
  "plot": "seaborn.scatterplot",
  "data": "penguins.csv",
  "args": {
    "hue": "Species",
    "x": "FlipperLengthMm",
    "y": "BodyMassG"
  }
}
```

```json
{
  "plot": "normal_probability_plot",
  "data": "penguins.csv",
  "args": {"column": "FlipperLengthMm"}
}
```

## Analysis orders

An analysis order is one dictionary with these fields:

    {
      data: exact filename string,
      analysis: concise nonfunction request label string,
      args: dictionary
    }

`analysis` is a concise semantic request label, not a Python function name. `args` must contain every variable, filter-independent parameter, grouping/category order, success category, hypothesis, confidence level, sample size, simulation count, prediction value, requested result component, and other explicit detail needed to perform the supplied request.

If the analysis requires filtering or transforming a dataset, replace the filename in `data` with the same inline data-selection dictionary used by plot orders:

    {
      data: {
        base: exact filename string,
        description: precise deterministic filter or transformation string
      },
      analysis: concise nonfunction request label string,
      args: dictionary
    }

The nested `data` dictionary is part of the same analysis order. Never emit a separate preprocessing order.

Common analysis labels include:

- Data inspection: `head`, `list_values`, `frequency_table`, `contingency_table`
- Descriptive statistics: `count`, `proportion`, `mean`, `median`, `mode`, `quantile`, `five_number_summary`, `variance`, `standard_deviation`, `iqr`, `summary_statistics`, `correlation`
- Normal models and simulation: `normal_probability`, `sampling_simulation`, `bootstrap`
- Confidence intervals: `one_proportion_confidence_interval`, `two_proportion_confidence_interval`, `one_mean_confidence_interval`, `two_mean_confidence_interval`, `paired_mean_confidence_interval`
- Hypothesis tests: `one_proportion_z_test`, `two_proportion_z_test`, `one_sample_t_test`, `two_sample_t_test`, `paired_t_test`, `chi_square_goodness_of_fit`, `chi_square_independence`, `anova`
- Regression: `simple_linear_regression`, `multiple_linear_regression`, `regression_prediction`, `regression_confidence_interval`, `regression_prediction_interval`, `regression_diagnostics`, `white_test`

If the supplied request is actionable but is not properly represented by one of these common labels, use a concise nonfunction label that faithfully names the requested result.

Examples:

```json
{
  "data": {
    "base": "penguins.csv",
    "description": "Keep only rows where Sex equals Male and Species equals Emperor."
  },
  "analysis": "list_values",
  "args": {"column": "FlipperLengthMm"}
}
```

```json
{
  "data": {
    "base": "penguins.csv",
    "description": "Keep only rows where Sex equals Male and Species equals Emperor."
  },
  "analysis": "mean",
  "args": {"column": "FlipperLengthMm"}
}
```

```json
{
  "data": "penguins.csv",
  "analysis": "two_sample_t_test",
  "args": {
    "alternative": "two-sided",
    "column": "FlipperLengthMm",
    "group_column": "Sex",
    "groups": ["Female", "Male"],
    "null_difference": 0
  }
}
```

```json
{
  "data": "penguins.csv",
  "analysis": "regression_prediction_interval",
  "args": {
    "confidence_level": 0.95,
    "outcome": "BodyMassG",
    "predictors": ["FlipperLengthMm", "Species"],
    "values": {"FlipperLengthMm": 200, "Species": "Adelie"}
  }
}
```

Return exactly one order as valid JSON. Do not include markdown fences, schema notation, commentary, or additional text.
