"""Human-readable Markdown reporting for prompt experiments."""

from pathlib import Path

from experiments.utils.charts import heatmap_filename, render_charts
from experiments.utils.results import ExperimentResults, TrialResult, trial_filename
from experiments.utils.summary import ExperimentSummary, build_summary
from experiments.evaluation.types import EvaluationRun, TestResult


def write_report(directory: Path, results: ExperimentResults) -> Path:
    """Write the report, summary, and SVG charts for an experiment."""
    summary = build_summary(results)
    (directory / "summary.json").write_text(
        summary.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    charts_directory = directory / "charts"
    charts_directory.mkdir(exist_ok=True)
    for name, chart in render_charts(results, summary).items():
        (charts_directory / name).write_text(chart, encoding="utf-8")
    path = directory / "report.md"
    path.write_text(render_report(results, summary), encoding="utf-8")
    return path


def concise_console_summary(results: ExperimentResults) -> list[str]:
    """Return the compact summary shown after an interactive experiment run."""
    summary = build_summary(results)
    lines = [
        "Experiment complete",
        _console_measure("Trials completed", f"{summary.completed}/{summary.trials}"),
        _console_measure(
            "Trials passing all criteria",
            f"{summary.fully_passed}/{summary.trials}",
        ),
        _console_measure(
            "OpenAI ratings passed",
            _fraction(summary.openai_passed, summary.openai_total),
        ),
        _console_measure(
            "JEV ratings passed",
            _fraction(summary.jev_passed, summary.jev_total),
        ),
        _console_measure(
            "Evaluator agreement",
            _fraction(summary.agreement, summary.agreement_total),
        ),
    ]
    if summary.errors:
        lines.append(_console_measure("Trial errors", str(summary.errors)))
    lines.append("  By scenario:")
    lines.extend(
        f"    {scenario.case_id}: {scenario.fully_passed}/{scenario.trials} "
        "trials passed"
        for scenario in summary.scenarios
    )
    return lines


def _console_measure(label: str, value: str) -> str:
    return f"  {label + ':':<30}{value}"


def render_report(
    results: ExperimentResults,
    summary: ExperimentSummary | None = None,
) -> str:
    """Render experiment results as a self-contained Markdown report."""
    report_summary = summary or build_summary(results)
    candidate_models, openai_evaluator_models, jev_evaluator_models = _models_used(
        results
    )
    lines = [
        f"# Experiment: {results.name}",
        "",
        "> This report shows model responses, evaluator ratings, confidence, and "
        "OpenAI rationales. Additional evidence and probabilities remain in the "
        "linked trial JSON.",
        "",
        "## Overview",
        "",
        f"- Created: `{results.created_at.isoformat()}`",
        f"- Source commit: `{results.source_commit or 'unavailable'}`",
        f"- Candidate: `{results.candidate.name}`",
        f"- Candidate model: {_format_models(candidate_models)}",
        f"- OpenAI evaluator model: {_format_models(openai_evaluator_models)}",
        f"- JEV evaluator model: {_format_models(jev_evaluator_models)}",
        f"- Repetitions: {results.repetitions}",
        f"- Trials passing every criterion: {report_summary.fully_passed}/{report_summary.trials}",
        f"- Trial errors: {report_summary.errors}",
        "- Artifacts: [combined JSON](results.json), [manifest](experiment.json), "
        "[machine summary](summary.json)",
        "",
        "A trial passes only when every selected OpenAI criterion passes.",
        "",
        "## Outcome measures",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| OpenAI ratings passed | {_fraction(report_summary.openai_passed, report_summary.openai_total)} |",
        f"| JEV ratings passed | {_fraction(report_summary.jev_passed, report_summary.jev_total)} |",
        f"| Evaluator agreement | {_fraction(report_summary.agreement, report_summary.agreement_total)} |",
        "",
        "## Evaluator agreement",
        "",
        "![OpenAI and JEV agreement matrix](charts/evaluator-agreement.svg)",
        "",
        "## Results by scenario",
        "",
        "| Scenario | Trials | Full passes | OpenAI ratings | JEV ratings | Agreement |",
        "|---|---:|---:|---:|---:|---:|",
        *_scenario_summary_rows(report_summary),
    ]
    indexed_trials = list(enumerate(results.trials, start=1))
    for scenario_index, scenario in enumerate(report_summary.scenarios, start=1):
        lines.extend(
            [
                "",
                f"## {scenario.name}",
                "",
                f"Scenario ID: `{scenario.case_id}`",
                "",
                f"![Criterion results by repetition](charts/{heatmap_filename(scenario.case_id, scenario_index)})",
                "",
                "### Trial results",
                "",
            ]
        )
        for trial_index, trial in indexed_trials:
            if trial.case_id == scenario.case_id:
                lines.extend(_trial_details(trial, trial_index))
    return "\n".join(lines)


def _models_used(results: ExperimentResults) -> tuple[list[str], list[str], list[str]]:
    candidate_models = [results.candidate.model]
    openai_evaluator_models: list[str] = []
    jev_evaluator_models: list[str] = []
    for trial in results.trials:
        evaluation = trial.evaluation
        if evaluation is None:
            continue
        _append_unique(candidate_models, evaluation["candidate_model"])
        _append_unique(
            openai_evaluator_models,
            evaluation["openai_evaluator_model"],
        )
        if "jev" in evaluation:
            _append_unique(jev_evaluator_models, evaluation["jev"]["model"])
    return candidate_models, openai_evaluator_models, jev_evaluator_models


def _append_unique(models: list[str], model: str) -> None:
    if model not in models:
        models.append(model)


def _format_models(models: list[str]) -> str:
    if not models:
        return "unavailable"
    return ", ".join(f"`{model}`" for model in models)


def _scenario_summary_rows(summary: ExperimentSummary) -> list[str]:
    return [
        f"| {_table_text(scenario.name)} (`{_table_text(scenario.case_id)}`) "
        f"| {scenario.completed}/{scenario.trials} "
        f"| {scenario.fully_passed}/{scenario.trials} "
        f"| {_fraction(scenario.openai_passed, scenario.openai_total)} "
        f"| {_fraction(scenario.jev_passed, scenario.jev_total)} "
        f"| {_fraction(scenario.agreement, scenario.agreement_total)} |"
        for scenario in summary.scenarios
    ]


def _trial_details(trial: TrialResult, index: int) -> list[str]:
    result = (
        "PASS"
        if trial.evaluation is not None and trial.evaluation["summary"]["passed"]
        else "ERROR"
        if trial.evaluation is None
        else "FAIL"
    )
    lines = [
        "<details>",
        f"<summary>Repetition {trial.repetition} — {result}</summary>",
        "",
        f"[Raw trial JSON](trials/{trial_filename(index, trial)})",
        "",
    ]
    if trial.error is not None:
        lines.extend(
            [
                f"**ERROR — `{trial.error.type}`**",
                "",
                trial.error.message,
                "",
                "</details>",
                "",
            ]
        )
        return lines
    if trial.evaluation is None:
        lines.extend(
            [
                "**ERROR — no evaluation was recorded.**",
                "",
                "</details>",
                "",
            ]
        )
        return lines

    evaluation = trial.evaluation
    lines.extend(
        [
            f"**{result}** — score: {evaluation['summary']['score']:.0%}; "
            f"duration: {trial.duration_seconds:.1f}s",
            "",
            f"- Response model: `{evaluation['candidate_model']}`",
            f"- OpenAI evaluator: `{evaluation['openai_evaluator_model']}`",
            f"- Candidate action: `{evaluation['candidate_action']}`",
        ]
    )
    if "jev" in evaluation:
        lines.append(f"- JEV evaluator: `{evaluation['jev']['model']}`")
    lines.extend(
        [
            "",
            "#### Tutor response",
            "",
            *_blockquote(evaluation["transcript"][-1]["message"]),
            "",
            "#### Evaluator results",
            "",
            *_evaluation_table(evaluation),
            "",
            "#### OpenAI rationales",
            "",
            *_rationales(evaluation),
            "",
            "</details>",
            "",
        ]
    )
    return lines


def _evaluation_table(evaluation: EvaluationRun) -> list[str]:
    lines = [
        "| Criterion | Suite | OpenAI | JEV | JEV confidence | Agreement |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, result in evaluation["tests"].items():
        jev_result = evaluation["jev"]["tests"].get(name) if "jev" in evaluation else None
        jev_rating = jev_result["rating"].upper() if jev_result is not None else "—"
        confidence = f"{jev_result['confidence']:.0%}" if jev_result is not None else "—"
        agreement = _agreement(result, jev_result["rating"] if jev_result is not None else None)
        lines.append(
            f"| {_label(name)} | {_label(result['suite'])} | "
            f"{result['rating'].upper()} | {jev_rating} | {confidence} | {agreement} |"
        )
    return lines


def _agreement(result: TestResult, jev_rating: str | None) -> str:
    if jev_rating is None:
        return "—"
    return "YES" if result["rating"] == jev_rating else "NO"


def _rationales(evaluation: EvaluationRun) -> list[str]:
    lines: list[str] = []
    for name, result in evaluation["tests"].items():
        lines.extend(
            [
                f"- **{_label(name)} — {result['rating'].upper()}**",
                f"  {result['rationale']}",
            ]
        )
    return lines


def _blockquote(value: str) -> list[str]:
    return [f"> {line}" if line else ">" for line in value.splitlines()]


def _table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _label(value: str) -> str:
    return _table_text(value.replace("_", " ").title())


def _fraction(value: int, total: int) -> str:
    if total == 0:
        return "0/0"
    return f"{value}/{total} ({value / total:.0%})"
