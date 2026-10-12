import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.gen_ai.completion import CompletionRequest, CompletionResult
from src.testing.prompt_evaluation.artifacts import (
    CandidateSnapshot,
    ExperimentArtifactWriter,
    ExperimentManifest,
    TrialArtifact,
    generation_observation,
)
from src.testing.prompt_evaluation.observation import (
    GenerationCompleted,
    TrialCapture,
)
from src.testing.prompt_evaluation.experiment_reporting import (
    build_experiment_summary,
    render_experiment_charts,
    render_experiment_report,
)
from src.testing.prompt_evaluation.run_experiment import _parse_arguments
from src.testing.prompt_evaluation.types import EvaluationRun, JevEvaluation


def test_writes_manifest_and_each_trial_only_once(tmp_path: Path) -> None:
    output_directory = tmp_path / "experiment"
    writer = ExperimentArtifactWriter(output_directory)
    manifest = ExperimentManifest(
        experiment_id="experiment-1",
        name="Artifact test",
        created_at=datetime.now(timezone.utc),
        source_commit="f9aaa9b",
        repetitions=1,
        concurrency=1,
        candidate=CandidateSnapshot(
            name="RubberDuck",
            prompt="Tutor prompt",
            requested_model="candidate-model",
            tools=["talk_to_user"],
            tool_schemas=[],
            tool_choice="auto",
            output_format=None,
            reasoning="low",
        ),
        evaluation_config={
            "evaluator_model": "evaluator-model",
            "standard_tests": {
                "accuracy": {
                    "definition": "Is it accurate?",
                    "metric": {
                        "pass": {"definition": "Accurate"},
                        "fail": {"definition": "Inaccurate"},
                    },
                }
            },
            "evaluator_prompt": "Evaluate it.",
        },
        rubber_duck_tests={},
        scenarios=[
            {
                "id": "case-1",
                "name": "Case one",
                "transcript": [{"role": "student", "message": "Help."}],
                "reference_answer": "Offer focused help.",
            }
        ],
    )
    writer.initialize(manifest)

    capture = TrialCapture()
    capture.observe(
        GenerationCompleted(
            request=CompletionRequest(
                model="candidate-model",
                instructions="Tutor prompt",
                input=[{"role": "user", "content": "Help."}],
                tools=[],
            ),
            result=CompletionResult(
                output=[
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "What have you tried?"}
                        ],
                    }
                ],
                usage={"input_tokens": 120, "output_tokens": 18},
                response_id="response-1",
                provider_model="candidate-model-version",
            ),
        )
    )
    result: EvaluationRun = {
        "transcript": [
            {"role": "student", "message": "Help."},
            {"role": "tutor", "message": "What have you tried?"},
        ],
        "candidate_action": "direct_message",
        "candidate_model": "candidate-model-version",
        "openai_evaluator_model": "evaluator-model-version",
        "tests": {
            "accuracy": {
                "rating": "pass",
                "evidence": ["What have you tried?"],
                "rationale": "The response is accurate.",
                "suite": "standard",
                "evaluator": "openai",
            },
            "exact_action": {
                "rating": "pass",
                "evidence": ["direct_message"],
                "rationale": "The expected action was used.",
                "suite": "case",
                "evaluator": "deterministic",
            },
        },
        "summary": {"passed": True, "score": 1.0, "blocking_tests": []},
        "reference_answer_used": True,
    }
    jev: JevEvaluation = {
        "model": "jev-test",
        "tests": {
            "accuracy": {
                "rating": "fail",
                "confidence": 0.91,
                "probabilities": {"pass": 0.09, "fail": 0.91},
                "suite": "standard",
            }
        },
        "selection": {
            "selected": [],
            "skipped": [],
            "uncertain": [],
            "applicability": {},
        },
        "summary": {
            "passed": False,
            "score": 0.0,
            "blocking_tests": ["accuracy"],
        },
    }
    now = datetime.now(timezone.utc)
    artifact = TrialArtifact(
        experiment_id="experiment-1",
        trial_id="trial-1",
        scenario_id="case-1",
        repetition=1,
        started_at=now,
        ended_at=now,
        duration_seconds=0.25,
        status="completed",
        generation=generation_observation(capture),
        jev=jev,
        evaluation=result,
        error=None,
    )

    trial_path = writer.write_trial(artifact)

    manifest_data = json.loads((output_directory / "experiment.json").read_text())
    trial_data = json.loads(trial_path.read_text())
    assert manifest_data["schema_version"] == "2"
    assert trial_data["schema_version"] == "2"
    assert manifest_data["candidate"]["prompt"] == "Tutor prompt"
    assert trial_data["generation"]["response_id"] == "response-1"
    assert trial_data["generation"]["output"][0]["type"] == "message"
    assert trial_data["evaluation"]["summary"]["passed"] is True
    summary = build_experiment_summary(manifest, [artifact])
    chart_paths = writer.write_charts(
        render_experiment_charts(manifest, [artifact], summary)
    )
    report = render_experiment_report(manifest, [artifact], summary)
    report_path = writer.write_report(report)
    summary_path = writer.write_summary(summary)
    assert "What have you tried?" in report_path.read_text()
    assert "The response is accurate." in report_path.read_text()
    assert "JEV probabilities: fail=0.91, pass=0.09" in report_path.read_text()
    assert "Criterion statistics" not in report_path.read_text()
    assert "Automated checks" in report_path.read_text()
    assert "Exact Action" in report_path.read_text()
    assert "charts/evaluator-agreement.svg" in report_path.read_text()
    assert "Trial duration" not in report_path.read_text()
    assert "Candidate token usage" not in report_path.read_text()
    assert "| Test | Repetition" not in report_path.read_text()
    assert len(chart_paths) == 2
    assert all(path.read_text().startswith("<svg") for path in chart_paths)
    heatmap = next(
        path.read_text()
        for path in chart_paths
        if path.name.startswith("criteria-")
    )
    assert "OpenAI" in heatmap
    assert "JEV" in heatmap
    assert "Local" not in heatmap
    assert "Exact Action" not in heatmap
    assert "≠" in heatmap
    summary_data = json.loads(summary_path.read_text())
    assert summary_data["schema_version"] == "1"
    assert summary_data["agreement"] == 0
    assert summary_data["openai_pass_jev_fail"] == 1
    assert summary_data["scenarios"][0]["average_input_tokens"] == 120
    assert summary_data["scenarios"][0]["criteria"][0][
        "average_jev_confidence"
    ] == 0.91
    with pytest.raises(FileExistsError):
        writer.write_trial(artifact)


def test_experiment_arguments_require_an_explicit_output_directory() -> None:
    with pytest.raises(ValueError, match="Usage"):
        _parse_arguments([])

    arguments = _parse_arguments(
        [
            "--output",
            "/tmp/experiment",
            "--repetitions",
            "4",
            "--concurrency",
            "2",
            "--case",
            "case-1",
        ]
    )

    assert arguments.output_directory == Path("/tmp/experiment")
    assert arguments.name == "ad-hoc-experiment"
    assert arguments.repetitions == 4
    assert arguments.concurrency == 2
    assert arguments.case_ids == ["case-1"]


def test_loads_named_experiment_configuration() -> None:
    arguments = _parse_arguments(
        ["experiments/configs/standard-duck-baseline.yaml"]
    )

    assert arguments.name == "standard-duck-baseline"
    assert arguments.repetitions == 3
    assert arguments.concurrency == 3
    assert arguments.case_ids is None
    assert arguments.detailed_console is False
    assert arguments.output_directory.parent == Path.cwd() / "experiments/runs"
