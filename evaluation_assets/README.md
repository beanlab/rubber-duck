# Prompt evaluator assets

This directory contains non-sensitive, development-only assets for the experimental prompt evaluator.

- `examples/` contains strict JSON fixtures for the offline pipeline.
- These fixtures test mechanics and obvious controls. They are not sealed evaluator-qualification data and cannot support claims about real tutoring prompts.
- Raw run artifacts belong under ignored `data/evaluations/`, not in this directory.

Run the smoke fixture with:

```bash
poetry run python scripts/prompt_eval.py offline \
  --fixture evaluation_assets/examples/offline-smoke.json \
  --output data/evaluations
```

The command performs no network calls and writes an aggregate JSON and Markdown report alongside immutable artifact envelopes.
