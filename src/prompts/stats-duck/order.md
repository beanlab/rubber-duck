# Canonical order stage

Convert the supplied analysis request into one canonical JSON order. Return JSON only, without markdown.

Use an exact filename from the supplied dataset metadata. Use exact column names in `data` and `args`. Never invent a dataset, column, operation, filter, or argument. The preceding decision stage has already established that the request is actionable.

## Dataset orders

```json
{"action": "list_datasets", "data": null}
```

```json
{"action": "describe_dataset", "data": "exact_filename.csv"}
```

## Plot orders

```json
{
  "plot": "histogram",
  "data": "exact_filename.csv",
  "args": {"x": "ExactColumn"}
}
```

If filtering or derived data is required, use:

```json
{
  "plot": "boxplot",
  "data": {
    "base": "exact_filename.csv",
    "description": "A precise deterministic data transformation"
  },
  "args": {"x": "ExactGroupColumn", "y": "ExactNumericColumn"}
}
```

Permitted plot names:

- `bar_chart`
- `histogram`
- `density_plot`
- `boxplot`
- `scatterplot`
- `normal_probability_plot`
- `residual_plot`

## Analysis orders

```json
{
  "data": "exact_filename.csv",
  "analysis": "mean",
  "args": {"column": "ExactColumn"}
}
```

Permitted analysis names:

- Data inspection: `head`, `frequency_table`, `contingency_table`
- Descriptive statistics: `count`, `proportion`, `mean`, `median`, `mode`, `quantile`, `five_number_summary`, `variance`, `standard_deviation`, `iqr`, `summary_statistics`, `correlation`
- Normal models and simulation: `normal_probability`, `sampling_simulation`, `bootstrap`
- Confidence intervals: `one_proportion_confidence_interval`, `two_proportion_confidence_interval`, `one_mean_confidence_interval`, `two_mean_confidence_interval`, `paired_mean_confidence_interval`
- Hypothesis tests: `one_proportion_z_test`, `two_proportion_z_test`, `one_sample_t_test`, `two_sample_t_test`, `paired_t_test`, `chi_square_goodness_of_fit`, `chi_square_independence`, `anova`
- Regression: `simple_linear_regression`, `multiple_linear_regression`, `regression_prediction`, `regression_confidence_interval`, `regression_prediction_interval`, `regression_diagnostics`, `white_test`

Put variable names, filters, groups, hypotheses, confidence levels, sample sizes, simulation counts, prediction values, and other explicit details in `args`. Omit unspecified optional arguments rather than choosing them. Keep argument keys and nested object keys in alphabetical order.

Requests about ethics, causation, study design, or interpreting results are not executable analyses and must not be mapped to an invented operation.