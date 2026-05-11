# Stats Duck Provides Statistical Outputs

## Purpose

Produce dataset-based statistics.

---

# Context

A student is in a private Stats Duck conversation thread.

---

# Action

The student asks for dataset information, statistical output, plots,
models, predictions, or unsupported help.

---

# Interaction

| Action | Outcome |
| --- | --- |
| Student asks what datasets are available. | Sends the available dataset list. |
| Student identifies exactly one dataset and requests summary statistics. | Returns labeled numeric output. |
| Student asks to display rows or a table. | Sends the requested table as a file. |
| Student asks for a plot of specified variables. | Sends a plot file with a title and labeled axes. |
| Student asks for regression output. | Returns the requested regression output without interpretation. |
| Student names a dataset ambiguously. | Asks which matching dataset the student means. |
| Student asks a yes/no, true/false, or multiple-choice question. | Says the request is outside scope and suggests a dataset-based statistical output. |
| Student asks for interpretation. | Says interpretation is outside scope and offers supported outputs instead. |

---

# Outcome

The Stats Duck produces requested statistical artifacts for available
datasets, clarifies ambiguous dataset references, and rejects
unsupported request types.

---

# Non-Goals

The Stats Duck does not interpret statistical meaning, answer
non-dataset questions, or proceed when the dataset is ambiguous.
