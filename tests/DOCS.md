## Purpose

`tests/` provides lightweight regression checks for SQL metrics persistence, Python tool output formatting behavior, rubric generation helpers, and prompt-response evaluation.

## Operational Flow

- `test_sql_metric_handlers.py` validates insert/read paths for `messages`, `usage`, and `feedback` via in-memory SQLite.
- `test_python_tools_formatting.py` validates numeric table formatting, blank handling, and scientific-notation suppression in rendered tool output.
- `test_rubricize.py` validates debugging-practice rubric helper behavior for line-numbered code fields, error-line extraction, and correct-code output.
- `tester_bot_tests/prompt_evaluation/test_helpers.py` validates fixed-prefix,
  single-response evaluation with a fake OpenAI client.
- `tester_bot_tests/prompt_evaluation/test_responses.py` runs one tutor response
  for each fixed prefix in `cases.yaml` and reports the anchored criterion ratings.
- `tester_bot_tests/test_dry_run.py` runs the standard, general-statistics,
  CS-statistics, and debugging-practice ducks through their existing live
  conversation assessments.
- `conftest.py` injects a minimal `quest` module shim so tests can import project modules without full runtime dependencies.

## Failure Modes and Guardrails

- Test coverage is intentionally narrow; most runtime subsystems are currently untested in this directory.
- Formatting tests assert string-level output contracts, so prompt/runtime formatting changes may require coordinated test updates.

Run the response-level prompt cases with `OPENAI_API_KEY` set:

```bash
poetry run pytest -s tests/tester_bot_tests/prompt_evaluation/test_responses.py
```

Use `-k <case-id>` to run one case. Add or remove cases in
`tests/tester_bot_tests/prompt_evaluation/cases.yaml`; no Python registration is
required.
