## Purpose

`tests/` contains application regression tests, pytest-based prompt tests, and
Discord end-to-end tests.

## Offline conversation tests

Run the deterministic suite without live prompt or Discord calls:

```bash
poetry run pytest -q -m 'not prompt_eval' --ignore=tests/tester_bot_tests
```

- `test_conversations.py` covers thread ownership, routing, concurrent starts,
  restart ordering, cancellation, and error reporting. Its integration test
  checks that replies reach the latest conversation in a reused thread.
- `stats_duck/test_workflow.py` contains Stats Duck's deterministic behavior tests,
  a real-Quest test of fresh history and separate metrics, and existing YAML prompt tests.
  Only its YAML cases carry the `prompt_eval` marker.

The two integration tests use `@with_real_quest` to run their async test functions
in fresh interpreters, avoiding the root `conftest.py` Quest stub. They use real
Quest and SQL with scripted Discord and model operations.

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
