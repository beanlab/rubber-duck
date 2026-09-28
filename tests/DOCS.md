## Purpose

`tests/` provides lightweight regression checks for SQL metrics persistence, Python tool output formatting behavior, rubric generation helpers, and the small prompt-evaluation runner.

## Operational Flow

- `test_sql_metric_handlers.py` validates insert/read paths for `messages`, `usage`, and `feedback` via in-memory SQLite.
- `test_python_tools_formatting.py` validates numeric table formatting, blank handling, and scientific-notation suppression in rendered tool output.
- `test_rubricize.py` validates debugging-practice rubric helper behavior for line-numbered code fields, error-line extraction, and correct-code output.
- `test_prompt_eval.py` validates the student–tutor tool loop and conversation evaluator with fake model responses.
- `conftest.py` injects a minimal `quest` module shim so tests can import project modules without full runtime dependencies.

## Failure Modes and Guardrails

- Test coverage is intentionally narrow; most runtime subsystems are currently untested in this directory.
- Formatting tests assert string-level output contracts, so prompt/runtime formatting changes may require coordinated test updates.
