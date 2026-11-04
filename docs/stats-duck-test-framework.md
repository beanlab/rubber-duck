# Stats Duck test framework

All tests are defined in `tests/stats_duck/cases.yaml` under one `cases:` list.
Adding a case does not require Python changes.

## Run modes

`run` controls how much of the system the case exercises:

```yaml
run: decision                 # one agent
run: order
run: coder
run: [decision, order]        # an agent sequence
run: [decision, order, coder]
run: full                     # public conversation workflow
```

## Shared dataset context

```yaml
contexts:
  nutrition:
    - filename: cereal.csv
      dataset_name: Cereal Nutrition Data
      path: /home/sandbox/datasets/cereal.csv
      description: |
        Dataset name: Cereal Nutrition Data
        Columns:
        - calories, integer, calories per serving
```

Each case references a context by name.

## Current coverage

The YAML suite includes single-agent decision, order, and coder checks;
multi-turn history; fixed and model handoffs; complete three-agent chains;
clarification; dataset listing and description; plot fulfillment; and scalar
analysis fulfillment.

## One-agent case

```yaml
- id: decide-histogram
  context: nutrition
  run: decision
  history:
    - role: user
      content: Make a histogram of calories from the cereal dataset.
  expect:
    decision:
      analysis_requested: true
      analysis_description:
        contains_all: [histogram, calories, cereal]
```

Order cases supply `analysis_description`. Coder cases supply `order`.

## Agent-sequence case

`history` is sent only to the decision agent. The production workflow does not
append the decision response as an assistant message for the next agent.
Instead, decision passes an `analysis_description` to order, and order passes
a structured `order` to coder. The test framework uses those same handoffs.

`handoff` controls what is passed between agents:

```yaml
handoff: fixed  # use predefined YAML values; later stages still run after a failure
handoff: model  # use a live response only when its assertion passes (default)
handoff: both   # evaluate both paths
```

For a fixed decision handoff, define `analysis_description`. For a fixed order
handoff, define `order`. These are inputs for the next agent; `expect` remains
the assertion against each live response.

- A fixed path continues after an earlier failure because its next input is
  already defined in YAML.
- A model path continues only when the preceding response passes its assertion.
- A blocked or failed path fails the case, but does not prevent fixed checks
  from completing.

```yaml
- id: decision-to-order
  context: nutrition
  run: [decision, order]
  handoff: both
  history:
    - role: user
      content: Make a histogram of calories from the cereal dataset.
  analysis_description: Create a histogram of calories from the cereal dataset.
  expect:
    decision:
      analysis_requested: true
      analysis_description:
        contains_all: [histogram, calories, cereal]
    order:
      plot: seaborn.histplot
      data: cereal.csv
      args:
        x: calories
```

With `both`, the report labels downstream checks as `order [fixed]` and
`order [model]`. If the decision fails, the fixed order check still runs and
the model path is reported as blocked.

For `[decision, order, coder]`, also add the predefined `order` at the case
root. The fixed coder receives it; the model coder receives the passing live
order response.

## Full workflow case

```yaml
- id: full-histogram
  context: nutrition
  run: full
  turns:
    - Make a histogram of calories from the cereal dataset.
  execution: image
  expect:
    images: 1
    code:
      contains_all: [histplot, calories, cereal.csv, savefig]
      excludes: ["```"]
```

For full cases, `execution` supplies a canned `text`, `image`, or `table`
sandbox result. Generated Python is syntax-checked but is not run in Podman.

Text expectations are case-insensitive and support:

```yaml
contains_all: [dataset, variable]
excludes: [cereal.csv]
question: true
```

## Running tests

```bash
poetry run pytest tests/stats_duck -m prompt_eval -vv -s
poetry run pytest tests/stats_duck -k decide-ready-histogram -vv -s
poetry run pytest tests/stats_duck -k decision-to-order -vv -s
poetry run pytest tests/stats_duck -k full -vv -s
poetry run pytest 'tests/stats_duck/test_workflow.py::test_case[decision-to-order]' -vv -s
```

The same case IDs appear in the pytest UI.
With `-s`, each case prints stage-level passed, failed, and blocked results as
the requests complete. `RUNNING` is flushed before every live request, so a
slow response is visible:

```text
[decision-to-order] handoff=both
  RUNNING decision
  PASSED  decision
          response: {...}
  RUNNING order [fixed]
  PASSED  order [fixed]
          response: {...}
  RUNNING order [model]
  PASSED  order [model]
          response: {...}
  RESULT  3/3 stages passed
```

Passing stages include the actual model response. Failures include the unmet
expectation and received value. Live requests have a 60-second timeout and no
hidden SDK retries.

## Typing correction

`MessageHandler.typing()` was declared as returning `None`, although production
uses it as an async context manager. Its protocol annotation now matches the
existing production behavior. This is a type-only correction.
