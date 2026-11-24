# Tests

`tests/` owns pytest cases, fixtures, scenarios, assertions, and application-driving code.
`evaluation/` owns experiments, grading, measurements, saved results, and reports.
Production workflows remain under `src/`.

## Layout

- `workflows/`: shared local application and message drivers (signatures),
  their planned contract tests, and the existing Discord process lifecycle.
- `ducks/test_application.py`: planned lifecycle journeys common to both ducks.
- `ducks/standard_duck/`: existing response evaluations, YAML cases/criteria,
  and Standard-specific response/workflow declarations.
- `ducks/stats_duck/`: native pytest stage, handoff, and delivery cases;
  test data/dependencies; and planned complete application/numerical checks.
- `discord/`: real Discord conversation tests, learner/assessor assets, and
  fixture wiring. Its reusable application process setup is in `workflows/`.
- `evaluation/`: implemented offline tests of evaluator/config/reporting code,
  plus declarations for planned grading, comparison, and subprocess contracts.

## Offline checks

```bash
poetry run pytest -q tests/evaluation tests/workflows tests/ducks -m 'not prompt_eval'
```

New workflow helpers and tests remain signature-only and explicitly skipped.
The root `conftest.py` stubs Quest; real local application tests must isolate
or correct that before they claim real workflow-manager coverage.

## Live response evaluations

```bash
poetry run pytest -m prompt_eval -s tests/ducks/standard_duck/test_responses.py
poetry run pytest -m prompt_eval -s tests/ducks/stats_duck
```

Standard response tests require `OPENAI_API_KEY` and `JEV_API_KEY`. Stats tests
require `OPENAI_API_KEY`. Use ordinary pytest `-k` selection to choose cases.
Standard case/config documentation is in `ducks/standard_duck/configs/README.md`.
Stats cases are `pytest.param` rows beside their assertions; there is no YAML
loader or configurable stage dispatcher. See the [Stats test guide](ducks/stats_duck/README.md)
for case authoring and the scope of its existing checks.

Existing Stats delivery tests call the production workflow with controlled
messages and a fake sandbox. They check code shape and artifact delivery;
`Analysis result.` is a canned value, not evidence of numerical correctness.
Known-data execution and real application routing remain planned coverage.

## Live Discord conversations

```bash
poetry run pytest -s tests/discord --config tests/discord/config.yaml
```

These tests need the configured Discord bot credentials and application
configuration. The default config uses the current Standard and Stats builders.
The legacy Debugging Practice scenario remains explicitly skipped until it has
a builder for the current startup API. Discord runs are not part of offline checks.

The existing Discord cost report still uses the entry-channel opener ID, while
the application now records usage under the thread start-marker ID. Application
costs in that report are incomplete until those IDs are correlated; a reported
zero does not establish zero usage.

See `evaluation/README.md` for the current experiment CLI and
`evaluation/docs/evaluation-design.md` for the intended shared workflow design.
