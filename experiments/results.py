"""The single persisted result produced by an experiment."""

import subprocess
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from tests.prompt_evaluation.types import EvaluationRun


class ResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Candidate(ResultModel):
    name: str
    prompt: str
    model: str
    tools: list[str]
    reasoning: str | None


class TrialError(ResultModel):
    type: str
    message: str


class TrialResult(ResultModel):
    case_id: str
    repetition: int
    duration_seconds: float
    evaluation: EvaluationRun | None
    error: TrialError | None


class ExperimentResults(ResultModel):
    name: str
    created_at: datetime
    source_commit: str | None
    repetitions: int
    candidate: Candidate
    trials: list[TrialResult]


def write_results(directory: Path, results: ExperimentResults) -> Path:
    """Create a result directory containing one readable JSON document."""
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "results.json"
    path.write_text(results.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def source_commit(root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip()
    return commit if completed.returncode == 0 and commit else None
