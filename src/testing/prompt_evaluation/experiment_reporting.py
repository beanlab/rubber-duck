"""Readable summaries for recorded prompt experiments."""

from collections.abc import Sequence
from html import escape
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.testing.prompt_evaluation.artifacts import (
    ExperimentManifest,
    TrialArtifact,
)
from src.testing.prompt_evaluation.types import EvaluationCase, TestResult


class CriterionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    suite: str
    primary_evaluator: Literal["openai", "deterministic", "unavailable"]
    primary_passed: int
    primary_total: int
    jev_passed: int
    jev_total: int
    agreement: int
    agreement_total: int
    openai_pass_jev_fail: int
    openai_fail_jev_pass: int
    average_jev_confidence: float | None
    primary_variable: bool
    jev_variable: bool
    selection_selected: int
    selection_total: int


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    name: str
    trials: int
    completed: int
    failed: int
    fully_passed: int
    openai_passed: int
    openai_total: int
    jev_passed: int
    jev_total: int
    agreement: int
    agreement_total: int
    average_duration_seconds: float
    median_duration_seconds: float
    minimum_duration_seconds: float
    maximum_duration_seconds: float
    average_input_tokens: float | None
    average_output_tokens: float | None
    average_response_characters: float
    criteria: list[CriterionSummary]


class ExperimentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    experiment_id: str
    name: str
    trials: int
    completed: int
    failed: int
    fully_passed: int
    openai_passed: int
    openai_total: int
    jev_passed: int
    jev_total: int
    agreement: int
    agreement_total: int
    openai_pass_jev_pass: int
    openai_pass_jev_fail: int
    openai_fail_jev_pass: int
    openai_fail_jev_fail: int
    scenarios: list[ScenarioSummary]


def build_experiment_summary(
    manifest: ExperimentManifest,
    trials: Sequence[TrialArtifact],
) -> ExperimentSummary:
    """Aggregate trials without discarding their detailed evidence."""
    scenario_summaries = [
        _scenario_summary(
            scenario,
            [trial for trial in trials if trial.scenario_id == scenario["id"]],
        )
        for scenario in manifest.scenarios
    ]
    confusion = _confusion_counts(trials)
    return ExperimentSummary(
        experiment_id=manifest.experiment_id,
        name=manifest.name,
        trials=len(trials),
        completed=sum(trial.status == "completed" for trial in trials),
        failed=sum(trial.status == "failed" for trial in trials),
        fully_passed=sum(
            trial.evaluation is not None
            and trial.evaluation["summary"]["passed"]
            for trial in trials
        ),
        openai_passed=sum(item.openai_passed for item in scenario_summaries),
        openai_total=sum(item.openai_total for item in scenario_summaries),
        jev_passed=sum(item.jev_passed for item in scenario_summaries),
        jev_total=sum(item.jev_total for item in scenario_summaries),
        agreement=sum(item.agreement for item in scenario_summaries),
        agreement_total=sum(item.agreement_total for item in scenario_summaries),
        openai_pass_jev_pass=confusion[0],
        openai_pass_jev_fail=confusion[1],
        openai_fail_jev_pass=confusion[2],
        openai_fail_jev_fail=confusion[3],
        scenarios=scenario_summaries,
    )


def render_experiment_report(
    manifest: ExperimentManifest,
    trials: Sequence[TrialArtifact],
    summary: ExperimentSummary,
) -> str:
    """Render a compact comparison report with collapsible trial evidence."""
    lines = [
        f"# Experiment: {manifest.name}",
        "",
        "> This report shows model responses and evaluator-provided evidence and "
        "rationales. JEV currently supplies ratings, confidence, and "
        "probabilities, but no textual rationale. Hidden chain-of-thought is not "
        "captured.",
        "",
        "## Overview",
        "",
        f"- Experiment ID: `{manifest.experiment_id}`",
        f"- Created: `{manifest.created_at.isoformat()}`",
        f"- Source commit: `{manifest.source_commit or 'unavailable'}`",
        f"- Candidate model: `{manifest.candidate.requested_model}`",
        f"- Scenarios: {len(manifest.scenarios)}",
        f"- Repetitions per scenario: {manifest.repetitions}",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Trials completed | {summary.completed}/{summary.trials} |",
        f"| Trials passing all checks | {summary.fully_passed}/{summary.trials} |",
        f"| OpenAI test ratings passed | {_fraction(summary.openai_passed, summary.openai_total)} |",
        f"| JEV test ratings passed | {_fraction(summary.jev_passed, summary.jev_total)} |",
        f"| Evaluator agreement | {_fraction(summary.agreement, summary.agreement_total)} |",
        "",
        "## Evaluator agreement",
        "",
        "Rows are OpenAI ratings and columns are JEV ratings. Green squares are "
        "agreements; orange squares are disagreements. Each number is a criterion "
        "judged by both evaluators.",
        "",
        "![OpenAI and JEV agreement matrix](charts/evaluator-agreement.svg)",
        "",
        "## Results by scenario",
        "",
        "| Scenario | Trials | Full passes | OpenAI tests | JEV tests | Agreement |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for scenario in summary.scenarios:
        lines.append(
            f"| {scenario.name} (`{scenario.scenario_id}`) "
            f"| {scenario.completed}/{scenario.trials} "
            f"| {scenario.fully_passed}/{scenario.trials} "
            f"| {_fraction(scenario.openai_passed, scenario.openai_total)} "
            f"| {_fraction(scenario.jev_passed, scenario.jev_total)} "
            f"| {_fraction(scenario.agreement, scenario.agreement_total)} |"
        )

    for scenario_index, scenario in enumerate(manifest.scenarios, start=1):
        scenario_trials = sorted(
            (trial for trial in trials if trial.scenario_id == scenario["id"]),
            key=lambda trial: trial.repetition,
        )
        lines.extend(
            _scenario_report(
                scenario,
                scenario_trials,
                scenario_index,
            )
        )

    return "\n".join(lines) + "\n"


def render_experiment_charts(
    manifest: ExperimentManifest,
    trials: Sequence[TrialArtifact],
    summary: ExperimentSummary,
) -> dict[str, str]:
    """Render small standalone SVGs that work in Markdown previews."""
    charts = {
        "evaluator-agreement.svg": _agreement_chart(summary),
    }
    for index, scenario in enumerate(manifest.scenarios, start=1):
        scenario_trials = sorted(
            (trial for trial in trials if trial.scenario_id == scenario["id"]),
            key=lambda trial: trial.repetition,
        )
        charts[_heatmap_name(scenario, index)] = _heatmap_chart(
            scenario,
            scenario_trials,
        )
    return charts


def _agreement_chart(summary: ExperimentSummary) -> str:
    cells = [
        ("OpenAI pass / JEV pass", summary.openai_pass_jev_pass, "#3b8f5a"),
        ("OpenAI pass / JEV fail", summary.openai_pass_jev_fail, "#d89028"),
        ("OpenAI fail / JEV pass", summary.openai_fail_jev_pass, "#d89028"),
        ("OpenAI fail / JEV fail", summary.openai_fail_jev_fail, "#b64b4b"),
    ]
    parts = [_svg_start(620, 430), _svg_title("OpenAI and JEV rating matrix")]
    parts.extend(
        [
            _svg_text(330, 55, "JEV", 18, "middle", True),
            _svg_text(285, 88, "Pass", 15, "middle", True),
            _svg_text(435, 88, "Fail", 15, "middle", True),
            _svg_text(95, 210, "OpenAI", 18, "middle", True),
            _svg_text(170, 145, "Pass", 15, "end", True),
            _svg_text(170, 295, "Fail", 15, "end", True),
        ]
    )
    positions = [(210, 105), (360, 105), (210, 255), (360, 255)]
    for (label, count, color), (x, y) in zip(cells, positions, strict=True):
        parts.append(
            f'<rect x="{x}" y="{y}" width="130" height="130" rx="8" '
            f'fill="{color}" opacity="0.86"><title>{escape(label)}: {count}</title></rect>'
        )
        parts.append(_svg_text(x + 65, y + 77, str(count), 34, "middle", True, "#fff"))
    parts.append(
        _svg_text(
            310,
            412,
            f"Paired judgments: {summary.agreement_total}",
            14,
            "middle",
            False,
            "#555",
        )
    )
    parts.append("</svg>\n")
    return "".join(parts)


def _heatmap_chart(
    scenario: EvaluationCase,
    trials: Sequence[TrialArtifact],
) -> str:
    names = _semantic_test_names(trials)
    label_width = 270
    evaluator_width = 76
    evaluator_gap = 6
    disagreement_gap = 24
    group_width = 190
    row_height = 38
    width = max(760, label_width + group_width * len(trials) + 24)
    height = 170 + row_height * max(1, len(names))
    parts = [_svg_start(width, height), _svg_title(scenario["name"])]
    parts.append(
        _svg_text(
            16,
            52,
            "Green: PASS · red: FAIL · gray: missing · orange outline and ≠: OpenAI/JEV disagreement",
            12,
            "start",
            False,
            "#555",
        )
    )
    for column, trial in enumerate(trials):
        group_x = label_width + column * group_width
        group_center = group_x + evaluator_width + evaluator_gap / 2
        parts.append(
            _svg_text(
                group_center,
                82,
                f"Repetition {trial.repetition}",
                13,
                "middle",
                True,
            )
        )
        parts.append(
            _svg_text(
                group_x + evaluator_width / 2,
                106,
                "OpenAI",
                11,
                "middle",
                True,
            )
        )
        parts.append(
            _svg_text(
                group_x + evaluator_width + evaluator_gap + evaluator_width / 2,
                106,
                "JEV",
                11,
                "middle",
                True,
            )
        )
    for row, name in enumerate(names):
        y = 122 + row * row_height
        parts.append(_svg_text(16, y + 21, _label(name), 12, "start"))
        for column, trial in enumerate(trials):
            x = label_width + column * group_width
            parts.extend(
                _heatmap_cells(
                    trial,
                    name,
                    x,
                    y,
                    evaluator_width,
                    evaluator_gap,
                    disagreement_gap,
                    29,
                )
            )
    if not names:
        parts.append(_svg_text(16, 140, "No completed judgments", 14, "start", False, "#777"))
    parts.append("</svg>\n")
    return "".join(parts)


def _heatmap_cells(
    trial: TrialArtifact,
    name: str,
    x: float,
    y: float,
    evaluator_width: float,
    evaluator_gap: float,
    disagreement_gap: float,
    height: float,
) -> list[str]:
    primary = _openai_result(trial, name)
    jev = trial.jev["tests"].get(name) if trial.jev is not None else None
    openai_rating = (
        primary["rating"]
        if primary is not None and primary["evaluator"] == "openai"
        else None
    )
    jev_rating = jev["rating"] if jev is not None else None
    openai_text = openai_rating.upper() if openai_rating is not None else "N/A"
    jev_text = jev_rating.upper() if jev_rating is not None else "N/A"
    jev_x = x + evaluator_width + evaluator_gap
    parts = _rating_cell(
        x,
        y,
        evaluator_width,
        height,
        openai_rating,
        openai_text,
    )
    parts.extend(
        _rating_cell(
            jev_x,
            y,
            evaluator_width,
            height,
            jev_rating,
            jev_text,
        )
    )
    disagrees = (
        primary is not None
        and primary["evaluator"] == "openai"
        and jev is not None
        and primary["rating"] != jev["rating"]
    )
    if disagrees:
        pair_width = evaluator_width * 2 + evaluator_gap
        parts.extend(
            [
                f'<rect x="{x - 3}" y="{y - 3}" width="{pair_width + 6}" '
                f'height="{height + 6}" rx="7" fill="none" stroke="#c87916" '
                'stroke-width="3"/>',
                _svg_text(
                    x + pair_width + disagreement_gap / 2,
                    y + height / 2 + 5,
                    "≠",
                    18,
                    "middle",
                    True,
                    "#b66b0b",
                ),
            ]
        )
    return parts


def _rating_cell(
    x: float,
    y: float,
    width: float,
    height: float,
    rating: str | None,
    label: str,
) -> list[str]:
    text_color = "#333" if rating is None else "#fff"
    return [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4" '
        f'fill="{_rating_color(rating)}"><title>{escape(label)}</title></rect>',
        _svg_text(
            x + width / 2,
            y + height / 2 + 4,
            label,
            11,
            "middle",
            True,
            text_color,
        ),
    ]


def _svg_start(width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        'style="font-family:system-ui,sans-serif">'
        f'<rect width="{width}" height="{height}" fill="#fff"/>'
    )


def _svg_title(title: str) -> str:
    return f"<title>{escape(title)}</title>" + _svg_text(16, 25, title, 18, "start", True)


def _svg_text(
    x: float,
    y: float,
    value: str,
    size: int,
    anchor: Literal["start", "middle", "end"],
    bold: bool = False,
    fill: str = "#222",
) -> str:
    weight = "600" if bold else "400"
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" fill="{fill}">{escape(value)}</text>'
    )


def _rating_color(rating: str | None) -> str:
    if rating == "pass":
        return "#4d9d69"
    if rating == "fail":
        return "#c85c5c"
    return "#d8d8d8"


def concise_console_summary(summary: ExperimentSummary) -> list[str]:
    """Return the small summary intended for an interactive terminal."""
    lines = [
        "Experiment complete",
        f"  Trials completed:          {summary.completed}/{summary.trials}",
        f"  Trials passing all gates:  {summary.fully_passed}/{summary.trials}",
        f"  OpenAI ratings passed:     {_fraction(summary.openai_passed, summary.openai_total)}",
        f"  JEV ratings passed:        {_fraction(summary.jev_passed, summary.jev_total)}",
        f"  Evaluator agreement:       {_fraction(summary.agreement, summary.agreement_total)}",
    ]
    lines.append("  By scenario:")
    lines.extend(
        f"    {scenario.scenario_id}: {scenario.fully_passed}/{scenario.trials} "
        "trials passed"
        for scenario in summary.scenarios
    )
    return lines


def _scenario_summary(
    scenario: EvaluationCase,
    trials: Sequence[TrialArtifact],
) -> ScenarioSummary:
    openai_passed = 0
    openai_total = 0
    jev_passed = 0
    jev_total = 0
    agreement = 0
    agreement_total = 0
    for trial in trials:
        if trial.evaluation is not None:
            semantic = _semantic_results(trial)
            openai_passed += sum(
                result["rating"] == "pass" for result in semantic.values()
            )
            openai_total += len(semantic)
        if trial.jev is not None:
            jev_passed += sum(
                result["rating"] == "pass" for result in trial.jev["tests"].values()
            )
            jev_total += len(trial.jev["tests"])
        agreed, compared = _agreement(trial)
        agreement += agreed
        agreement_total += compared
    durations = [trial.duration_seconds for trial in trials]
    input_tokens = _usage_values(trials, "input_tokens")
    output_tokens = _usage_values(trials, "output_tokens")
    response_characters = [
        len(_candidate_response(trial))
        for trial in trials
        if trial.evaluation is not None
    ]
    return ScenarioSummary(
        scenario_id=scenario["id"],
        name=scenario["name"],
        trials=len(trials),
        completed=sum(trial.status == "completed" for trial in trials),
        failed=sum(trial.status == "failed" for trial in trials),
        fully_passed=sum(
            trial.evaluation is not None
            and trial.evaluation["summary"]["passed"]
            for trial in trials
        ),
        openai_passed=openai_passed,
        openai_total=openai_total,
        jev_passed=jev_passed,
        jev_total=jev_total,
        agreement=agreement,
        agreement_total=agreement_total,
        average_duration_seconds=(sum(durations) / len(durations) if durations else 0),
        median_duration_seconds=median(durations) if durations else 0,
        minimum_duration_seconds=min(durations) if durations else 0,
        maximum_duration_seconds=max(durations) if durations else 0,
        average_input_tokens=_average(input_tokens),
        average_output_tokens=_average(output_tokens),
        average_response_characters=(
            sum(response_characters) / len(response_characters)
            if response_characters
            else 0
        ),
        criteria=[
            _criterion_summary(name, trials)
            for name in _test_names_with_selection(trials)
        ],
    )


def _criterion_summary(
    name: str,
    trials: Sequence[TrialArtifact],
) -> CriterionSummary:
    primary_results = [
        result
        for trial in trials
        if (result := _openai_result(trial, name)) is not None
    ]
    jev_results = [
        result
        for trial in trials
        if trial.jev is not None
        and (result := trial.jev["tests"].get(name)) is not None
    ]
    paired = [
        (openai, jev)
        for trial in trials
        if (openai := _openai_result(trial, name)) is not None
        and openai["evaluator"] == "openai"
        and trial.jev is not None
        and (jev := trial.jev["tests"].get(name)) is not None
    ]
    evaluators = {result["evaluator"] for result in primary_results}
    if "openai" in evaluators:
        primary_evaluator: Literal["openai", "deterministic", "unavailable"] = (
            "openai"
        )
    elif "deterministic" in evaluators:
        primary_evaluator = "deterministic"
    else:
        primary_evaluator = "unavailable"
    suites = [result["suite"] for result in primary_results]
    suites.extend(result["suite"] for result in jev_results)
    is_selection_criterion = any(
        trial.jev is not None
        and name in trial.jev["selection"]["applicability"]
        for trial in trials
    )
    selection_trials = (
        [trial for trial in trials if trial.jev is not None]
        if is_selection_criterion
        else []
    )
    return CriterionSummary(
        name=name,
        suite=suites[0] if suites else "rubber_duck",
        primary_evaluator=primary_evaluator,
        primary_passed=sum(result["rating"] == "pass" for result in primary_results),
        primary_total=len(primary_results),
        jev_passed=sum(result["rating"] == "pass" for result in jev_results),
        jev_total=len(jev_results),
        agreement=sum(openai["rating"] == jev["rating"] for openai, jev in paired),
        agreement_total=len(paired),
        openai_pass_jev_fail=sum(
            openai["rating"] == "pass" and jev["rating"] == "fail"
            for openai, jev in paired
        ),
        openai_fail_jev_pass=sum(
            openai["rating"] == "fail" and jev["rating"] == "pass"
            for openai, jev in paired
        ),
        average_jev_confidence=_average(
            [result["confidence"] for result in jev_results]
        ),
        primary_variable=len({result["rating"] for result in primary_results}) > 1,
        jev_variable=len({result["rating"] for result in jev_results}) > 1,
        selection_selected=sum(
            name in trial.jev["selection"]["selected"]
            for trial in selection_trials
            if trial.jev is not None
        ),
        selection_total=len(selection_trials),
    )


def _scenario_report(
    scenario: EvaluationCase,
    trials: Sequence[TrialArtifact],
    scenario_index: int,
) -> list[str]:
    lines = [
        "",
        f"## {scenario['name']}",
        "",
        f"Scenario ID: `{scenario['id']}`",
        "",
        "### Evaluator results by repetition",
        "",
        f"![Criterion results by repetition](charts/{_heatmap_name(scenario, scenario_index)})",
        "",
    ]
    lines.extend(_automated_checks(trials))

    lines.extend(["", "### Candidate responses", ""])
    for trial in trials:
        lines.extend(_response_details(trial))

    lines.extend(["", "### Detailed results", ""])
    for trial in trials:
        lines.extend(_trial_details(trial))
    return lines


def _response_details(trial: TrialArtifact) -> list[str]:
    status = _trial_label(trial)
    response = _candidate_response(trial)
    action = (
        trial.evaluation["candidate_action"]
        if trial.evaluation is not None
        else "unavailable"
    )
    return [
        "<details>",
        f"<summary>Repetition {trial.repetition} — {status} — action: {action}</summary>",
        "",
        *_blockquote(response),
        "",
        f"[Raw trial JSON](trials/{trial.trial_id}.json)",
        "",
        "</details>",
        "",
    ]


def _trial_details(trial: TrialArtifact) -> list[str]:
    lines = [
        "<details>",
        f"<summary>Repetition {trial.repetition} — {_trial_label(trial)} — evaluator evidence</summary>",
        "",
        f"- Trial ID: `{trial.trial_id}`",
        f"- Raw evidence: [JSON](trials/{trial.trial_id}.json)",
    ]
    if trial.evaluation is not None:
        lines.extend(
            [
                f"- Candidate model: `{trial.evaluation['candidate_model']}`",
                f"- OpenAI evaluator model: `{trial.evaluation['openai_evaluator_model']}`",
            ]
        )
    if trial.jev is not None:
        lines.append(f"- JEV evaluator model: `{trial.jev['model']}`")
    if trial.error is not None:
        lines.extend(
            [
                f"- Error type: `{trial.error.type}`",
                f"- Error: {trial.error.message}",
                "",
                "</details>",
                "",
            ]
        )
        return lines

    lines.extend(
        [
            "",
            "#### Candidate response",
            "",
            *_blockquote(_candidate_response(trial)),
            "",
            "#### Test judgments",
            "",
        ]
    )
    for name in _test_names([trial]):
        lines.extend(_test_details(trial, name))

    if trial.jev is not None and trial.jev["selection"]["applicability"]:
        lines.extend(
            [
                "#### JEV applicability decisions",
                "",
                "| Test | Decision | Confidence | Probabilities |",
                "|---|---|---:|---|",
            ]
        )
        for name, decision in trial.jev["selection"]["applicability"].items():
            lines.append(
                f"| {_label(name)} | {decision['outcome']} "
                f"| {decision['confidence']:.2f} "
                f"| {_probabilities(decision['probabilities'])} |"
            )
        lines.append("")

    lines.extend(["</details>", ""])
    return lines


def _test_details(trial: TrialArtifact, name: str) -> list[str]:
    openai = _openai_result(trial, name)
    jev = trial.jev["tests"].get(name) if trial.jev is not None else None
    lines = [f"##### {_label(name)}", ""]
    suite = (
        openai["suite"]
        if openai is not None
        else jev["suite"]
        if jev is not None
        else "unknown"
    )
    lines.append(f"- Suite: `{suite}`")
    if openai is not None:
        evaluator = "OpenAI" if openai["evaluator"] == "openai" else "Exact check"
        lines.append(f"- **{evaluator}: {openai['rating'].upper()}**")
        if openai["evidence"]:
            lines.append("- Evidence:")
            lines.extend(f"  - `{_inline(item)}`" for item in openai["evidence"])
        lines.append(f"- Rationale: {openai['rationale']}")
    if jev is not None:
        lines.extend(
            [
                f"- **JEV: {jev['rating'].upper()}**",
                f"- JEV confidence: {jev['confidence']:.2f}",
                f"- JEV probabilities: {_probabilities(jev['probabilities'])}",
            ]
        )
        if openai is not None and openai["evaluator"] == "openai":
            agreement = "yes" if openai["rating"] == jev["rating"] else "no"
            lines.append(f"- Evaluators agree: **{agreement}**")
    lines.append("")
    return lines


def _test_names(trials: Sequence[TrialArtifact]) -> list[str]:
    names: list[str] = []
    for trial in trials:
        if trial.evaluation is not None:
            for name in trial.evaluation["tests"]:
                if name not in names:
                    names.append(name)
        if trial.jev is not None:
            for name in trial.jev["tests"]:
                if name not in names:
                    names.append(name)
    return names


def _semantic_test_names(trials: Sequence[TrialArtifact]) -> list[str]:
    names: list[str] = []
    for trial in trials:
        if trial.evaluation is not None:
            for name, result in trial.evaluation["tests"].items():
                if result["evaluator"] == "openai" and name not in names:
                    names.append(name)
        if trial.jev is not None:
            for name in trial.jev["tests"]:
                if name not in names:
                    names.append(name)
    return names


def _automated_checks(trials: Sequence[TrialArtifact]) -> list[str]:
    names: list[str] = []
    for trial in trials:
        if trial.evaluation is None:
            continue
        for name, result in trial.evaluation["tests"].items():
            if result["evaluator"] == "deterministic" and name not in names:
                names.append(name)
    if not names:
        return []

    lines = [
        "### Automated checks",
        "",
        "These are exact programmatic checks, not model judgments.",
        "",
        "| Check | "
        + " | ".join(f"Repetition {trial.repetition}" for trial in trials)
        + " |",
        "|---|" + "---:|" * len(trials),
    ]
    for name in names:
        outcomes: list[str] = []
        for trial in trials:
            result = _openai_result(trial, name)
            outcomes.append(
                result["rating"].upper()
                if result is not None and result["evaluator"] == "deterministic"
                else "Not run"
            )
        lines.append(f"| {_label(name)} | " + " | ".join(outcomes) + " |")
    lines.append("")
    return lines


def _test_names_with_selection(trials: Sequence[TrialArtifact]) -> list[str]:
    names = _test_names(trials)
    for trial in trials:
        if trial.jev is None:
            continue
        for name in trial.jev["selection"]["applicability"]:
            if name not in names:
                names.append(name)
    return names


def _semantic_results(trial: TrialArtifact) -> dict[str, TestResult]:
    if trial.evaluation is None:
        return {}
    return {
        name: result
        for name, result in trial.evaluation["tests"].items()
        if result["evaluator"] == "openai"
    }


def _openai_result(trial: TrialArtifact, name: str) -> TestResult | None:
    if trial.evaluation is None:
        return None
    return trial.evaluation["tests"].get(name)


def _agreement(trial: TrialArtifact) -> tuple[int, int]:
    if trial.jev is None:
        return 0, 0
    semantic = _semantic_results(trial)
    compared = set(semantic) & set(trial.jev["tests"])
    agreed = sum(
        semantic[name]["rating"] == trial.jev["tests"][name]["rating"]
        for name in compared
    )
    return agreed, len(compared)


def _confusion_counts(trials: Sequence[TrialArtifact]) -> tuple[int, int, int, int]:
    pass_pass = 0
    pass_fail = 0
    fail_pass = 0
    fail_fail = 0
    for trial in trials:
        if trial.jev is None:
            continue
        semantic = _semantic_results(trial)
        for name in set(semantic) & set(trial.jev["tests"]):
            openai_rating = semantic[name]["rating"]
            jev_rating = trial.jev["tests"][name]["rating"]
            if openai_rating == "pass" and jev_rating == "pass":
                pass_pass += 1
            elif openai_rating == "pass" and jev_rating == "fail":
                pass_fail += 1
            elif openai_rating == "fail" and jev_rating == "pass":
                fail_pass += 1
            else:
                fail_fail += 1
    return pass_pass, pass_fail, fail_pass, fail_fail


def _candidate_response(trial: TrialArtifact) -> str:
    if trial.evaluation is None or not trial.evaluation["transcript"]:
        return "Candidate response unavailable."
    return trial.evaluation["transcript"][-1]["message"]


def _trial_label(trial: TrialArtifact) -> str:
    if trial.error is not None:
        return "ERROR"
    if trial.evaluation is None:
        return "INCOMPLETE"
    return "PASS" if trial.evaluation["summary"]["passed"] else "FAIL"


def _fraction(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{numerator}/{denominator} ({numerator / denominator:.0%})"


def _probabilities(probabilities: dict[str, float]) -> str:
    return ", ".join(
        f"{name}={probability:.2f}"
        for name, probability in sorted(probabilities.items())
    )


def _numeric_usage(trial: TrialArtifact, key: str) -> float | None:
    if trial.generation is None or trial.generation.usage is None:
        return None
    value = trial.generation.usage.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _usage_values(
    trials: Sequence[TrialArtifact],
    key: str,
) -> list[float]:
    return [
        value
        for trial in trials
        if (value := _numeric_usage(trial, key)) is not None
    ]


def _average(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _heatmap_name(scenario: EvaluationCase, index: int) -> str:
    normalized = "".join(
        character if character.isalnum() else "-"
        for character in scenario["id"].lower()
    )
    safe_id = "-".join(part for part in normalized.split("-") if part)
    return f"criteria-{index:02d}-{safe_id or 'scenario'}.svg"


def _blockquote(text: str) -> list[str]:
    lines = text.splitlines() or [""]
    return [f"> {line}" if line else ">" for line in lines]


def _inline(text: str) -> str:
    return text.replace("`", "'").replace("\n", " ")


def _label(name: str) -> str:
    return name.replace("_", " ").title()
