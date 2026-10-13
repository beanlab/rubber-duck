# Experiments

This directory contains repeated-experiment orchestration, runnable experiment
specifications, scripts, and generated results. The prompt tests it executes
live under `tests/prompt_evaluation/`; reusable OpenAI and JEV services remain
under `src/gen_ai/`.

Run the live YAML cases as pytest tests:

```bash
./experiments/test
```

Run a repeated experiment:

```bash
./experiments/run experiments/configs/standard-duck-baseline.yaml
```

An experiment runs the same prompt-test cases sequentially and writes one
`results.json` file under `experiments/results/`. Add prompt cases and criteria
under `tests/prompt_evaluation/`.
