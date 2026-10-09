## Purpose

`tests/` provides lightweight regression checks for SQL metrics persistence, Python tool output formatting behavior, rubric generation helpers, and prompt-response evaluation.

## Operational Flow

- `test_sql_metric_handlers.py` validates insert/read paths for `messages`, `usage`, and `feedback` via in-memory SQLite.
- `test_python_tools_formatting.py` validates numeric table formatting, blank handling, and scientific-notation suppression in rendered tool output.
- `test_rubricize.py` validates debugging-practice rubric helper behavior for line-numbered code fields, error-line extraction, and correct-code output.
- `tester_bot_tests/prompt_evaluation/test_evaluation.py` validates fixed-prefix,
  single-response evaluation with a fake OpenAI client.
- `tester_bot_tests/prompt_evaluation/test_responses.py` runs one tutor response
  for each fixed prefix using the production Standard Duck agent configuration
  and reports the anchored criterion ratings.
- `tester_bot_tests/test_dry_run.py` runs the standard, general-statistics,
  CS-statistics, and debugging-practice ducks through their existing live
  conversation assessments.
- `conftest.py` injects a minimal `quest` module shim so tests can import project modules without full runtime dependencies.

## Failure Modes and Guardrails

- Test coverage is intentionally narrow; most runtime subsystems are currently untested in this directory.
- Formatting tests assert string-level output contracts, so prompt/runtime formatting changes may require coordinated test updates.

Run the response-level prompt cases with `OPENAI_API_KEY` set. When
`JEV_API_KEY` is also set, the same responses are evaluated by OpenAI and JEV:

```bash
poetry run pytest -s tests/tester_bot_tests/prompt_evaluation/test_responses.py
```

Use `-k <case-id>` to run one case. Add or remove cases in
`tests/tester_bot_tests/prompt_evaluation/cases.yaml`. A case's optional `tests`
mapping adds case-specific criteria. General criteria are `standard_tests` in
`config.yaml`; Standard Duck behavior criteria are in `rubber_duck_tests.yaml`.
The report labels all three suites and the actual generator, OpenAI evaluator,
and JEV evaluator models. JEV first selects applicable response/action criteria;
JEV and OpenAI then evaluate the same selected model-judged criteria. Trajectory
criteria are skipped by the fixed-prefix runner.

Run the full suite concurrently, with a maximum of three active cases:

```bash
poetry run dotenv run -- python -m src.testing.prompt_evaluation.run_suite \
  live --concurrency 3
```

For a full or nightly run, prepare candidates and JEV selections concurrently,
then submit only the selected model-evaluated tests through OpenAI Batch:

```bash
poetry run dotenv run -- python -m src.testing.prompt_evaluation.run_suite \
  batch --concurrency 3
```

Each invocation generates and judges new responses. It does not cache or reuse
results. The Batch command waits for the asynchronous OpenAI job to finish. Add
`--case <case-id>` to either suite command to run one case.

Ordinary pytest and suite runs do not persist evaluation artifacts. To run an
explicit experiment with fresh repetitions and immutable JSON evidence, provide
a new output directory:

```bash
poetry run dotenv run -- python -m src.testing.prompt_evaluation.run_experiment \
  --output /tmp/rubber-duck-experiment \
  --repetitions 3 \
  --concurrency 3
```

The experiment runner writes one `experiment.json` manifest and one file per
trial under `trials/`. The output directory must not already exist. Use
`--case <case-id>` to limit the experiment to one configured case. Recording is
enabled only through this runner; regular tests retain their existing behavior.

Run the standard-duck Discord end-to-end test with two bot tokens in `.env`:

```dotenv
DISCORD_TOKEN=<rubber-duck-bot-token>
ACTOR_TOKEN=<tester-bot-token>
```

Add the tester bot's user ID to `bot-friends` in the local config, then run:

```bash
poetry run dotenv run -- pytest -s -q \
  tests/tester_bot_tests/test_dry_run.py::test_standard_duck_dry_run \
  --config local-testing-configs/local_<name>_config.yaml
```

The test starts and stops the app and creates a private Discord thread. Do not
run the app separately. The statistics tests additionally require the configured
Docker sandbox.
