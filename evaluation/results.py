"""The single persisted result produced by an experiment."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from evaluation.standard_duck.types import EvaluationRun


if TYPE_CHECKING:
    from pytest import TestReport


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
    case_name: str | None = None
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


class ExperimentManifest(ResultModel):
    schema_version: Literal["1"] = "1"
    name: str
    created_at: datetime
    source_commit: str | None
    repetitions: int
    candidate: Candidate
    cases: list[str]


def write_results(directory: Path, results: ExperimentResults) -> Path:
    """Create the structured experiment artifacts and return the combined JSON."""
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "results.json"
    path.write_text(results.model_dump_json(indent=2) + "\n", encoding="utf-8")
    _write_structured_artifacts(directory, results)
    return path


def write_structured_artifacts(directory: Path, results: ExperimentResults) -> None:
    """Write the manifest and individual trials, including when backfilling a run."""
    directory.mkdir(parents=True, exist_ok=True)
    _write_structured_artifacts(directory, results)


def _write_structured_artifacts(directory: Path, results: ExperimentResults) -> None:
    manifest = ExperimentManifest(
        name=results.name,
        created_at=results.created_at,
        source_commit=results.source_commit,
        repetitions=results.repetitions,
        candidate=results.candidate,
        cases=list(dict.fromkeys(trial.case_id for trial in results.trials)),
    )
    (directory / "experiment.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    trials_directory = directory / "trials"
    trials_directory.mkdir(exist_ok=True)
    for index, trial in enumerate(results.trials, start=1):
        (trials_directory / trial_filename(index, trial)).write_text(
            trial.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )


def trial_filename(index: int, trial: TrialResult) -> str:
    """Return a stable, filesystem-safe filename for one recorded trial."""
    safe_case = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in trial.case_id
    ).strip("-")
    return f"{index:03d}-{safe_case or 'case'}-r{trial.repetition}.json"


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


# Persist trial identity and provenance before execution can fail.
def start_trial(directory: Path, metadata: dict) -> dict:
    ...


# Incrementally persist an event and its artifacts without losing earlier evidence.
def record_event(trial: dict, event: dict) -> None:
    ...


# Attach setup, call, and teardown outcomes to the corresponding recorded trial.
def record_pytest_outcome(report: TestReport) -> None:
    ...


# Reconcile saved records with planned attempts, including missing and interrupted cases.
def collect_results(plan: dict, directory: Path) -> list[dict]:
    ...


# Compare compatible trials using fixed denominators and explicit incomplete-result rules.
def compare_trials(plan: dict, trials: list[dict]) -> dict:
    ...


class UsageCollector:
    def __init__(self):
        self.rows = []

    async def record_usage(
        self,
        guild_id,
        parent_channel_id,
        conversation_id,
        user_id,
        model,
        input_tokens,
        output_tokens,
        cached_tokens=0,
        reasoning_tokens=0,
    ):
        self.rows.append({
            "guild_id": guild_id,
            "parent_channel_id": parent_channel_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "model": model,
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "cached_tokens": int(cached_tokens or 0),
            "reasoning_tokens": int(reasoning_tokens or 0),
        })
