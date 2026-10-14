# Experiments

This directory contains repeated-experiment orchestration, experiment
specifications, and generated artifacts. The evaluation cases and criteria it
uses live under `tests/prompt_tests/configs/`.

Each YAML file under `configs/` defines one experiment. It declares the response,
OpenAI evaluator, and JEV models; selects cases; and sets the repetition count.
`cases` accepts `all` or a list of exact IDs from
`tests/prompt_tests/configs/cases.yaml`. The complete list of supported config
fields is documented in `configs/README.md`.

Run an experiment by name:

```bash
./experiments/run standard-duck-baseline
```

An explicit YAML path also works:

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

Result, summary, report, and chart helpers live under `utils/`; the shared
response-evaluation pipeline lives under `evaluation/`.
