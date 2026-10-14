# Experiments

This directory contains repeated-experiment orchestration, runnable experiment
specifications, scripts, and generated results. The prompt-test suite it executes
lives under `tests/prompt_tests/suite/`; reusable OpenAI and JEV services remain
under `src/gen_ai/`.

Run the live YAML cases as pytest tests:

```bash
./experiments/test
```

Run a repeated experiment:

```bash
./experiments/run experiments/configs/standard-duck-baseline.yaml
```

An experiment runs the same prompt-test cases sequentially and writes a result
directory under `experiments/results/` containing:

- `report.md` with readable results and embedded SVG charts
- `charts/` with evaluator agreement and per-scenario heatmaps
- `results.json` with the complete combined result
- `summary.json` with aggregate measurements
- `experiment.json` with the experiment manifest
- `trials/` with one JSON artifact per trial

Add prompt cases and criteria under `tests/prompt_tests/suite/`. The live,
model-backed pytest entry point remains at `tests/prompt_tests/test_responses.py`;
offline framework tests live under `tests/prompt_tests/deterministic/`.
