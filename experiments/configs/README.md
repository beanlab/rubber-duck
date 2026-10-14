# Experiment configuration reference

Each YAML file in this directory defines one experiment. Unknown fields are
rejected.

## Complete schema

| Field | Required | Accepted value | Default |
|---|---|---|---|
| `name` | yes | Non-empty string used in reports and generated directory names | — |
| `models.response` | yes | OpenAI model used to generate the tutor response | — |
| `models.evaluator` | yes | OpenAI model used to grade semantic criteria | — |
| `models.jev` | yes | JEV model used for conditional selection and comparison ratings | — |
| `cases` | no | `all` or a non-empty list of unique case IDs | `all` |
| `repetitions` | no | Integer of at least 1 | `1` |
| `output_directory` | no | Output path, relative to the repository root or absolute | Timestamped directory under `experiments/results/` |

Case IDs are defined in `tests/prompt_tests/configs/cases.yaml`. Unknown IDs are
rejected before an experiment starts.

## Complete example

```yaml
name: standard-duck-baseline

models:
  response: gpt-5.6-luna
  evaluator: gpt-5.6-sol
  jev: jev-latest

cases:
  - image-flip-clarification
  - contradictory-pytest-evidence

repetitions: 3
output_directory: experiments/results/standard-duck-baseline
```
