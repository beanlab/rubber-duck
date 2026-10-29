"""Small standalone SVG charts for experiment Markdown reports."""

from html import escape
from typing import Literal

from experiments.utils.results import ExperimentResults, TrialResult
from experiments.utils.summary import ExperimentSummary
from experiments.evaluation.types import TestOutcome


def render_charts(
    results: ExperimentResults,
    summary: ExperimentSummary,
) -> dict[str, str]:
    """Render the agreement matrix and one evaluator heatmap per case."""
    charts = {"evaluator-agreement.svg": _agreement_chart(summary)}
    case_ids = list(dict.fromkeys(trial.case_id for trial in results.trials))
    for index, case_id in enumerate(case_ids, start=1):
        trials = [trial for trial in results.trials if trial.case_id == case_id]
        name = next(
            (trial.case_name for trial in trials if trial.case_name is not None),
            case_id,
        )
        charts[heatmap_filename(case_id, index)] = _heatmap_chart(name, trials)
    return charts


def heatmap_filename(case_id: str, index: int) -> str:
    normalized = "".join(
        character if character.isalnum() else "-" for character in case_id.lower()
    )
    safe_id = "-".join(part for part in normalized.split("-") if part)
    return f"criteria-{index:02d}-{safe_id or 'case'}.svg"


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


def _heatmap_chart(name: str, trials: list[TrialResult]) -> str:
    criteria = _semantic_test_names(trials)
    label_width = 270
    evaluator_width = 76
    evaluator_gap = 6
    group_width = 190
    row_height = 38
    width = max(760, label_width + group_width * len(trials) + 24)
    height = 170 + row_height * max(1, len(criteria))
    parts = [_svg_start(width, height), _svg_title(name)]
    parts.append(
        _svg_text(
            16,
            52,
            "Green: PASS · red: FAIL · gray: missing · orange outline: disagreement",
            12,
            "start",
            False,
            "#555",
        )
    )
    for column, trial in enumerate(trials):
        group_x = label_width + column * group_width
        group_center = group_x + evaluator_width + evaluator_gap / 2
        parts.extend(
            [
                _svg_text(
                    group_center,
                    82,
                    f"Repetition {trial.repetition}",
                    13,
                    "middle",
                    True,
                ),
                _svg_text(
                    group_x + evaluator_width / 2,
                    106,
                    "OpenAI",
                    11,
                    "middle",
                    True,
                ),
                _svg_text(
                    group_x + evaluator_width + evaluator_gap + evaluator_width / 2,
                    106,
                    "JEV",
                    11,
                    "middle",
                    True,
                ),
            ]
        )
    for row, criterion in enumerate(criteria):
        y = 122 + row * row_height
        parts.append(_svg_text(16, y + 21, _label(criterion), 12, "start"))
        for column, trial in enumerate(trials):
            x = label_width + column * group_width
            parts.extend(
                _heatmap_cells(
                    trial,
                    criterion,
                    x,
                    y,
                    evaluator_width,
                    evaluator_gap,
                    29,
                )
            )
    if not criteria:
        parts.append(
            _svg_text(16, 140, "No completed judgments", 14, "start", False, "#777")
        )
    parts.append("</svg>\n")
    return "".join(parts)


def _heatmap_cells(
    trial: TrialResult,
    name: str,
    x: float,
    y: float,
    width: float,
    gap: float,
    height: float,
) -> list[str]:
    evaluation = trial.evaluation
    primary = evaluation["tests"].get(name) if evaluation is not None else None
    jev = (
        evaluation["jev"]["tests"].get(name)
        if evaluation is not None and "jev" in evaluation
        else None
    )
    openai_rating: TestOutcome | None = (
        primary["rating"]
        if primary is not None and primary["evaluator"] == "openai"
        else None
    )
    jev_rating = jev["rating"] if jev is not None else None
    jev_x = x + width + gap
    parts = _rating_cell(x, y, width, height, openai_rating)
    parts.extend(_rating_cell(jev_x, y, width, height, jev_rating))
    if openai_rating is not None and jev_rating is not None and openai_rating != jev_rating:
        pair_width = width * 2 + gap
        parts.extend(
            [
                f'<rect x="{x - 3}" y="{y - 3}" width="{pair_width + 6}" '
                f'height="{height + 6}" rx="7" fill="none" stroke="#c87916" '
                'stroke-width="3"/>',
                _svg_text(
                    x + pair_width + 12,
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
    rating: TestOutcome | None,
) -> list[str]:
    label = rating.upper() if rating is not None else "N/A"
    text_color = "#333" if rating is None else "#fff"
    return [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4" '
        f'fill="{_rating_color(rating)}"><title>{label}</title></rect>',
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


def _semantic_test_names(trials: list[TrialResult]) -> list[str]:
    names: list[str] = []
    for trial in trials:
        if trial.evaluation is None:
            continue
        for name, result in trial.evaluation["tests"].items():
            if result["evaluator"] == "openai" and name not in names:
                names.append(name)
    return names


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


def _rating_color(rating: TestOutcome | None) -> str:
    if rating == "pass":
        return "#4d9d69"
    if rating == "fail":
        return "#c85c5c"
    return "#d8d8d8"


def _label(name: str) -> str:
    return name.replace("_", " ").title()
