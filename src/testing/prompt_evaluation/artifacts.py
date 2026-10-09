"""Immutable artifacts for explicitly requested prompt experiments."""

import subprocess
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter
from typesafe_sdk import JSONContent, JSONValue

from src.gen_ai.gen_ai import Agent
from src.testing.prompt_evaluation.observation import TrialCapture
from src.testing.prompt_evaluation.types import (
    EvaluationCase,
    EvaluationConfig,
    EvaluationRun,
    JevEvaluation,
    RubberDuckTestConfig,
)


SCHEMA_VERSION: Literal["1"] = "1"

_JSON_VALUE = TypeAdapter(JSONValue)
_JSON_OBJECT = TypeAdapter(JSONContent)


def json_value(value: object) -> JSONValue:
    """Validate an SDK/config value before placing it in an artifact."""
    return _JSON_VALUE.validate_python(value)


def json_object(value: object) -> JSONContent:
    """Validate a mapping before placing it in an artifact."""
    return _JSON_OBJECT.validate_python(value)


class ArtifactModel(BaseModel):
    """Strict base for versioned experiment artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CandidateSnapshot(ArtifactModel):
    name: str
    prompt: str
    requested_model: str
    tools: list[str]
    tool_schemas: list[JSONContent]
    tool_choice: JSONValue
    output_format: str | None
    reasoning: str | None


class ExperimentManifest(ArtifactModel):
    schema_version: Literal["1"] = SCHEMA_VERSION
    experiment_id: str
    created_at: datetime
    source_commit: str | None
    repetitions: int
    concurrency: int
    candidate: CandidateSnapshot
    evaluation_config: EvaluationConfig
    rubber_duck_tests: dict[str, RubberDuckTestConfig]
    scenarios: list[EvaluationCase]


class GenerationObservation(ArtifactModel):
    requested_model: str
    provider_model: str | None
    response_id: str | None
    model_input: JSONValue
    output: list[JSONValue]
    usage: JSONContent | None


class TrialError(ArtifactModel):
    type: str
    message: str


class TrialArtifact(ArtifactModel):
    schema_version: Literal["1"] = SCHEMA_VERSION
    experiment_id: str
    trial_id: str
    scenario_id: str
    repetition: int
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    status: Literal["completed", "failed"]
    generation: GenerationObservation | None
    jev: JevEvaluation | None
    evaluation: EvaluationRun | None
    error: TrialError | None


def candidate_snapshot(
    agent: Agent,
    tool_schemas: Sequence[object],
) -> CandidateSnapshot:
    """Capture the resolved candidate used by every trial in an experiment."""
    output_format = (
        agent.output_format.__name__ if agent.output_format is not None else None
    )
    return CandidateSnapshot(
        name=agent.name,
        prompt=agent.prompt,
        requested_model=agent.model,
        tools=list(agent.tools),
        tool_schemas=[json_object(schema) for schema in tool_schemas],
        tool_choice=json_value(agent.tool_settings),
        output_format=output_format,
        reasoning=agent.reasoning,
    )


def generation_observation(capture: TrialCapture) -> GenerationObservation | None:
    """Convert captured completion evidence into a serializable snapshot."""
    event = capture.generation
    if event is None:
        return None

    usage = event.result.usage
    if usage is None:
        usage_data = None
    elif isinstance(usage, BaseModel):
        usage_data = json_object(usage.model_dump(mode="json"))
    else:
        usage_data = json_object(usage)
    return GenerationObservation(
        requested_model=event.request.model,
        provider_model=event.result.provider_model,
        response_id=event.result.response_id,
        model_input=json_value(event.request.input),
        output=[json_value(item) for item in event.result.output],
        usage=usage_data,
    )


def current_source_commit(root: Path) -> str | None:
    """Return the current Git commit when the runner is inside a worktree."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    commit = completed.stdout.strip()
    return commit or None


class ExperimentArtifactWriter:
    """Write each artifact once into a newly created experiment directory."""

    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory
        self.trials_directory = output_directory / "trials"

    def initialize(self, manifest: ExperimentManifest) -> None:
        self.output_directory.mkdir(parents=True, exist_ok=False)
        self.trials_directory.mkdir()
        self._write_new(self.output_directory / "experiment.json", manifest)

    def write_trial(self, artifact: TrialArtifact) -> Path:
        path = self.trials_directory / f"{artifact.trial_id}.json"
        self._write_new(path, artifact)
        return path

    @staticmethod
    def _write_new(path: Path, artifact: ArtifactModel) -> None:
        with path.open("x", encoding="utf-8") as artifact_file:
            artifact_file.write(artifact.model_dump_json(indent=2))
            artifact_file.write("\n")
