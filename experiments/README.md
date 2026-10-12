# Prompt experiments

Experiment specifications live in `experiments/configs/`. Run one from the
repository root:

```bash
./experiment experiments/configs/standard-duck-baseline.yaml
```

Unless `output_directory` is set in the specification, results are written to a
new timestamped directory under `experiments/runs/`. That directory is ignored
by Git but remains visible in editors such as VS Code.

Each run contains:

- `report.md`: readable comparisons and expandable evidence for every trial;
- `charts/*.svg`: dependency-free evaluator-agreement and criterion-result
  visuals embedded by the report;
- `summary.json`: aggregate machine-readable measurements;
- `experiment.json`: the resolved candidate, cases, criteria, and provenance;
- `trials/*.json`: complete immutable evidence for individual trials.

Each criterion heatmap has explicit OpenAI and JEV columns for every repetition.
An orange outline and `≠` mark a disagreement. Exact programmatic checks appear
separately under "Automated checks." Open the Markdown preview and expand a
trial to see the candidate response, OpenAI evidence and rationale, JEV
confidence and probabilities, and the raw JSON link.

The readable report intentionally stays simple. Derived statistics, raw timing,
and token usage remain available in `summary.json` and the trial JSON evidence
for later analysis.
