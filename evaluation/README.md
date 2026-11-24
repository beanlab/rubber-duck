# Evaluation

This is the single home for evaluation tooling, experiment configurations, and
related design and research documents. Production code stays under `src/`;
pytest cases, fixtures, scenarios, assertions, and shared application drivers
stay under `tests/`. `evaluation/` has no application/workflow test runner; planned
workflow experiments invoke the tests through pytest.

## Current implementation and planned workflow APIs

The existing Standard response evaluator, repeated experiment runner, reports,
and token cost calculation are implemented. Discord test drivers live under
`tests/discord/`, and shared application drivers live under `tests/workflows/`.

The shared application workflow APIs in `tests/workflows/application.py` and
`tests/workflows/messages.py`, plus the new event, comparison, grading, and
pytest orchestration functions remain signature-only proposals. Their tests under
`tests/evaluation/`, `tests/workflows/`, and `tests/ducks/` are explicitly skipped.
Implemented evaluator and preserved live response/delivery tests remain runnable.
The proposed local workflow driver is not executable yet.

## Layout

- `experiment.py`: the existing experiment CLI and planned pytest orchestration helpers.
- `config.py` and `configs/`: experiment specifications and validation.
- `standard_duck/responses.py`: existing Standard response behavior evaluation;
  adjacent modules provide criteria, provider adaptation, and result contracts.
- `results.py`: saved experiment artifacts and planned workflow evidence APIs.
- `reporting/`: Markdown reports, aggregate summaries, and SVG charts.
- `grading.py`: conversation assessments, their schemas, and planned grading APIs.
- `pricing.py`: estimated token cost calculation.
- `docs/`: [documentation index](docs/README.md),
  [evaluation design](docs/evaluation-design.md), and dated research references.
  The general [application flow](../docs/application-flow.md) lives under `docs/`.

## Run an existing prompt experiment

From the repository root:

```bash
./evaluation/run standard-duck-baseline
./evaluation/run evaluation/configs/standard-duck-baseline.yaml
```

Each specification selects cases, response/evaluator models, and repetitions.
Cases and criteria still come from `tests/ducks/standard_duck/configs/`.
See the [configuration reference](configs/README.md).
`OPENAI_API_KEY` and `JEV_API_KEY` are required for a live experiment.

The existing runner calls the response evaluation pipeline directly. The design
replaces that with execution of the same pytest evaluations used individually;
that change remains to be implemented.

Reports are written under `evaluation/results/` by default: `report.md`,
`results.json`, `summary.json`, `experiment.json`, individual `trials/`, and
SVG `charts/`. Saved runs were preserved during the move. Generated `results/`
and `runs/`, along with downloaded research PDFs under `docs/papers/`, are
ignored by Git. The paper source manifest remains versionable. Evaluation
files are excluded from the production Docker build context.

## Offline checks

```bash
poetry run pytest tests/evaluation
```

Live Discord cases live under `tests/discord/` and use shared process lifecycle
code under `tests/workflows/`. They use the grading and measurement helpers here.
They require Discord bot credentials and a compatible application
configuration. The default configuration selects current production builders;
the legacy Debugging Practice case is skipped until its builder exists.
