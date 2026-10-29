"""Regression tests for human-readable experiment artifacts."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from experiments.evaluation.console import print_prompt_summary
from experiments.evaluation.types import EvaluationCase, EvaluationRun
from experiments.utils.report import (
    concise_console_summary,
    render_report,
    write_report,
)
from experiments.utils.results import (
    Candidate,
    ExperimentResults,
    TrialResult,
    write_results,
)


def _results() -> ExperimentResults:
    evaluation: EvaluationRun = {
        "transcript": [
            {"role": "student", "message": "Why did this fail?"},
            {"role": "tutor", "message": "What does the function return?"},
        ],
        "candidate_action": "talk_to_user",
        "candidate_model": "candidate-model",
        "openai_evaluator_model": "evaluator-model",
        "tests": {
            "usefulness": {
                "rating": "pass",
                "evidence": ["focused question"],
                "rationale": "The question advances the investigation.",
                "suite": "standard",
                "evaluator": "openai",
            },
        },
        "summary": {"passed": True, "score": 1.0, "blocking_tests": []},
        "reference_answer_used": True,
        "jev": {
            "model": "jev-model",
            "tests": {
                "usefulness": {
                    "rating": "pass",
                    "confidence": 0.9,
                    "probabilities": {"pass": 0.9, "fail": 0.1},
                    "suite": "standard",
                }
            },
            "selection": {
                "selected": [],
                "skipped": [],
                "uncertain": [],
                "applicability": {},
            },
            "summary": {"passed": True, "score": 1.0, "blocking_tests": []},
        },
    }
    return ExperimentResults(
        name="baseline",
        created_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
        source_commit="abc123",
        repetitions=1,
        candidate=Candidate(
            name="Standard Duck",
            prompt="Be helpful.",
            model="candidate-model",
            tools=["talk_to_user"],
            reasoning=None,
        ),
        trials=[
            TrialResult(
                case_id="example-case",
                repetition=1,
                duration_seconds=1.25,
                evaluation=evaluation,
                error=None,
            )
        ],
    )


def test_render_report_includes_results_and_evidence() -> None:
    report = render_report(_results())

    assert "# Experiment: baseline" in report
    assert "Candidate model: `candidate-model`" in report
    assert "OpenAI evaluator model: `evaluator-model`" in report
    assert "JEV evaluator model: `jev-model`" in report
    assert "Trials passing every criterion: 1/1" in report
    assert "What does the function return?" in report
    assert "Usefulness — PASS" in report
    assert "The question advances the investigation." in report
    assert "| Usefulness | Standard | PASS | PASS | 90% | YES |" in report
    assert "<summary>Repetition 1 — PASS</summary>" in report
    assert "## Candidate prompt" not in report
    assert "JEV probabilities" not in report


def test_concise_console_summary_omits_trial_details() -> None:
    summary = concise_console_summary(_results())

    assert summary == [
        "Experiment complete",
        "  Trials completed:             1/1",
        "  Trials passing all criteria:  1/1",
        "  OpenAI ratings passed:        1/1 (100%)",
        "  JEV ratings passed:           1/1 (100%)",
        "  Evaluator agreement:          1/1 (100%)",
        "  By scenario:",
        "    example-case: 1/1 trials passed",
    ]


def test_write_report_creates_markdown_artifact(tmp_path: Path) -> None:
    directory = tmp_path / "experiment"
    results = _results()
    result_path = write_results(directory, results)
    path = write_report(directory, results)

    assert result_path == directory / "results.json"
    assert path == directory / "report.md"
    assert path.read_text(encoding="utf-8").startswith("# Experiment: baseline\n")
    assert (directory / "experiment.json").is_file()
    assert (directory / "summary.json").is_file()
    assert (directory / "trials/001-example-case-r1.json").is_file()
    assert (directory / "charts/evaluator-agreement.svg").is_file()
    assert (directory / "charts/criteria-01-example-case.svg").is_file()


def test_prompt_summary_lists_every_case(
    capsys: pytest.CaptureFixture[str],
) -> None:
    evaluation = _results().trials[0].evaluation
    assert evaluation is not None
    failed_evaluation: EvaluationRun = {
        **evaluation,
        "summary": {
            "passed": False,
            "score": 0.5,
            "blocking_tests": ["usefulness"],
        },
    }
    cases: list[EvaluationCase] = [
        {
            "id": "passing-case",
            "name": "Passing case",
            "transcript": [],
            "reference_answer": "",
        },
        {
            "id": "failing-case",
            "name": "Failing case",
            "transcript": [],
            "reference_answer": "",
        },
    ]

    print_prompt_summary([evaluation, failed_evaluation], cases=cases)

    output = capsys.readouterr().out
    assert "PASS  passing-case (1/1 checks passed)" in output
    assert "FAIL  failing-case (0/1 checks passed)" in output
    assert "Cases passed: 1/2" in output
