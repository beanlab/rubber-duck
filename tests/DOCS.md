## Purpose

`tests/` contains application regression tests, pytest-based prompt tests, and
Discord end-to-end tests.

## Prompt tests

Prompt tests use the normal pytest infrastructure. Offline framework tests are
under `tests/prompt_tests/deterministic/`; live model-backed tests are marked
`prompt_eval`. They run when both required API keys are available and otherwise
skip with a clear reason.

Run the offline prompt-test coverage with:

```bash
poetry run pytest tests/prompt_tests/deterministic
```

Run the live, paid prompt evaluations with:

```bash
poetry run pytest \
  -m prompt_eval \
  -s \
  tests/prompt_tests/test_responses.py
```

`OPENAI_API_KEY` and `JEV_API_KEY` are required for live evaluations. Use
standard pytest options such as `-k contradictory` to select individual cases.

The YAML evaluation definitions and their complete field reference are under
`tests/prompt_tests/configs/`.

## Discord end-to-end tests

Discord tests remain under `tests/tester_bot_tests/`. They require the relevant
bot credentials and application configuration; see that directory's fixtures
for supported command-line options.
