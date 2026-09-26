"""Redacted-by-default comparison reporting."""

from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path

from .schemas import ComparisonSummary, canonical_json


def render_markdown_report(summary: ComparisonSummary) -> str:
    safe_question = html.escape(summary.question, quote=True).replace("\n", " ")
    lines = [
        f"# Prompt evaluation report: {summary.run_id}",
        "",
        f"**Question:** {safe_question}",
        "",
        f"**Decision:** `{summary.decision}`",
        "",
        summary.decision_reason,
        "",
        "## Coverage",
        "",
        f"- Scenarios: {summary.scenario_count}",
        f"- Source families: {summary.source_family_count}",
        f"- Trials: {summary.trial_count}",
        f"- Candidates: `{summary.candidate_a_id}` and `{summary.candidate_b_id}`",
        "",
        "## Criterion results",
        "",
        "| Criterion | Expected | Compared | A better | B better | Ties | Unavailable |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in summary.results:
        lines.append(
            f"| `{result.criterion_id}` | {result.expected_pairs} | "
            f"{result.compared_pairs} | {result.candidate_a_better} | "
            f"{result.candidate_b_better} | {result.ties} | "
            f"{result.unavailable_pairs} |"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in summary.limitations)
    lines.extend(
        [
            "",
            "This standard report contains aggregate results and artifact IDs only. "
            "It does not include raw learner or candidate content.",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="x",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(content)
        temp_file.flush()
        os.fsync(temp_file.fileno())
    try:
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_reports(summary: ComparisonSummary, output_directory: str | Path) -> tuple[Path, Path]:
    output_directory = Path(output_directory)
    json_path = output_directory / "summary.json"
    markdown_path = output_directory / "report.md"
    _atomic_write(json_path, canonical_json(summary) + "\n")
    _atomic_write(markdown_path, render_markdown_report(summary))
    return json_path, markdown_path
