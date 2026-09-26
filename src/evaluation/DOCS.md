# Experimental prompt evaluator

`src/evaluation` contains the Discord-independent evidence core for the prompt evaluator prototype.

## Current scope

- Strict, versioned candidates, scenarios, declarations, trials, observations, and comparison summaries.
- Prompt-only treatment-isolation validation.
- Immutable JSON artifact envelopes with content digests and safe filesystem identifiers.
- Recorded-response import explicitly marked as non-causal.
- Deterministic request/evidence integrity grading.
- Paired ordinal comparison that returns only `inconclusive` or `invalid` at this stage.
- Aggregate JSON and Markdown reports that omit raw learner and candidate content.

The current package does not call a model, use Discord, qualify an LLM judge, or make a deployment recommendation.

## Offline example

```bash
poetry run python scripts/prompt_eval.py offline \
  --fixture evaluation_assets/examples/offline-smoke.json \
  --output data/evaluations
```

The output contains immutable artifact envelopes under `artifacts/` and rebuildable reports under `reports/`. `data/` is ignored, but private-data use still requires the privacy, retention, egress, and deletion controls described in the implementation plan.

## Main modules

- `schemas.py`: strict Pydantic evidence contracts and canonical digests.
- `artifacts.py`: path-safe atomic artifact persistence and integrity verification.
- `adapters/recorded.py`: imports development fixtures without claiming prompt causality.
- `grading.py`: checks that a trial matches its declaration and contains required evidence.
- `comparison.py`: validates trial/observation provenance and computes paired descriptive counts.
- `reporting.py`: writes redacted aggregate reports.
- `lifecycle.py`: validates run and trial state transitions.

The standalone completion adapter and semantic evaluator are later phases. They must satisfy the conformance and qualification gates in the implementation plan before their evidence can influence a real prompt decision.
