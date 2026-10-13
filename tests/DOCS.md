## Purpose

`tests/` contains application regression tests, pytest-based prompt tests, and
Discord end-to-end tests.

## Prompt tests

Prompt cases, evaluator criteria, pytest coverage, and the live pytest entry
point live in `tests/prompt_tests/`. Run the paid tests explicitly with:

```bash
./experiments/test
```

Experiment repetition and persisted results are separate concerns owned by
`experiments/`; see `experiments/README.md`.

## Discord end-to-end tests

Discord tests remain under `tests/tester_bot_tests/`. They require the relevant
bot credentials and application configuration; see that directory's fixtures
for supported command-line options.
