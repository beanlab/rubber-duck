# Prompt-test configuration reference

The three YAML files in this directory define the shared evaluators, test
criteria, and cases used by live prompt tests and repeated experiments.

## `config.yaml`

| Field | Required | Accepted value | Default |
|---|---|---|---|
| `evaluator_model` | yes | OpenAI model name used for semantic grading | — |
| `jev_model` | no | JEV model name used for selection and comparison ratings | `jev-latest` |
| `standard_tests` | yes | Mapping of criterion names to criterion definitions; at least one is required | — |
| `evaluator_prompt` | yes | Instructions shared by the OpenAI and JEV evaluators | — |
| `use_reference_answer` | no | Boolean controlling whether case reference answers are shown to evaluators | `true` |

Every entry under `standard_tests` has this shape:

```yaml
criterion_name:
  definition: The question the evaluator should answer.
  evaluator_prompt: Optional criterion-specific instructions.
  metric:
    pass:
      definition: A precise passing condition.
    fail:
      definition: A precise failing condition.
```

`evaluator_prompt` on an individual criterion is optional and supplements the
shared evaluator instructions.

## `cases.yaml`

The root `cases` field is a list. Every case supports:

| Field | Required | Accepted value |
|---|---|---|
| `id` | yes | Unique non-empty identifier used by pytest and experiment configs |
| `name` | yes | Human-readable case name |
| `transcript` | yes | Ordered list of `{role, message}` turns |
| `reference_answer` | yes | Evaluator-only facts and expected behavior |
| `tests` | no | Case-specific criteria using the same criterion shape as `standard_tests` |

Transcript roles are `student` and `tutor`. A fixed-prefix transcript must end
with a student turn; every tutor turn must be followed by a student turn.

## `rubber_duck_tests.yaml`

The root `rubber_duck_tests` field maps criterion names to reusable Rubber Duck
criteria. Every criterion has:

| Field | Required | Accepted value |
|---|---|---|
| `selection` | yes | `always` or `conditional` |
| `definition` | yes | The question the evaluator should answer |
| `metric.pass.definition` | yes | A precise passing condition |
| `metric.fail.definition` | yes | A precise failing condition |
| `evaluator_prompt` | no | Criterion-specific evaluator instructions |

`always` evaluates the criterion for every response. `conditional` asks JEV to
inspect the conversation prefix first; its `definition` must state the condition
that makes the criterion applicable.

All enabled Rubber Duck criteria are evaluated by OpenAI and JEV.
