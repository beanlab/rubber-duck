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
from src.testing.prompt_evaluation.run_experiment import _parse_arguments
from src.testing.prompt_evaluation.types import EvaluationRun


def test_writes_manifest_and_each_trial_only_once(tmp_path: Path) -> None:
    output_directory = tmp_path / "experiment"
    writer = ExperimentArtifactWriter(output_directory)
    manifest = ExperimentManifest(
        experiment_id="experiment-1",
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
            }
        },
        "summary": {"passed": True, "score": 1.0, "blocking_tests": []},
        "reference_answer_used": True,
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
        jev=None,
        evaluation=result,
        error=None,
    )

    trial_path = writer.write_trial(artifact)

    manifest_data = json.loads((output_directory / "experiment.json").read_text())
    trial_data = json.loads(trial_path.read_text())
    assert manifest_data["candidate"]["prompt"] == "Tutor prompt"
    assert trial_data["generation"]["response_id"] == "response-1"
    assert trial_data["generation"]["output"][0]["type"] == "message"
    assert trial_data["evaluation"]["summary"]["passed"] is True
    with pytest.raises(FileExistsError):
        writer.write_trial(artifact)


def test_experiment_arguments_require_an_explicit_output_directory() -> None:
    with pytest.raises(ValueError, match="--output is required"):
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
    assert arguments.repetitions == 4
    assert arguments.concurrency == 2
    assert arguments.case_id == "case-1"
