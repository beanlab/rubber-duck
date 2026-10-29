"""Aggregate experiment outcomes for reports and machine-readable summaries."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from experiments.utils.results import ExperimentResults, TrialResult


class SummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScenarioSummary(SummaryModel):
    case_id: str
    name: str
    trials: int
    completed: int
    errors: int
    fully_passed: int
    openai_passed: int
    openai_total: int
    jev_passed: int
    jev_total: int
    agreement: int
    agreement_total: int
    average_duration_seconds: float


class ExperimentSummary(SummaryModel):
    schema_version: Literal["1"] = "1"
    name: str
    trials: int
    completed: int
    errors: int
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


@dataclass
class _Counts:
    completed: int = 0
    errors: int = 0
    fully_passed: int = 0
    openai_passed: int = 0
    openai_total: int = 0
    jev_passed: int = 0
    jev_total: int = 0
    agreement: int = 0
    agreement_total: int = 0
    openai_pass_jev_pass: int = 0
    openai_pass_jev_fail: int = 0
    openai_fail_jev_pass: int = 0
    openai_fail_jev_fail: int = 0

    def include(self, trial: TrialResult) -> None:
        if trial.error is not None:
            self.errors += 1
        if trial.evaluation is None:
            return
        self.completed += 1
        self.fully_passed += trial.evaluation["summary"]["passed"]
        for name, result in trial.evaluation["tests"].items():
            self.openai_total += 1
            self.openai_passed += result["rating"] == "pass"
            if "jev" not in trial.evaluation:
                continue
            jev_result = trial.evaluation["jev"]["tests"].get(name)
            if jev_result is None:
                continue
            self.jev_total += 1
            self.jev_passed += jev_result["rating"] == "pass"
            self.agreement_total += 1
            self.agreement += result["rating"] == jev_result["rating"]
            pair = (result["rating"], jev_result["rating"])
            self.openai_pass_jev_pass += pair == ("pass", "pass")
            self.openai_pass_jev_fail += pair == ("pass", "fail")
            self.openai_fail_jev_pass += pair == ("fail", "pass")
            self.openai_fail_jev_fail += pair == ("fail", "fail")


def build_summary(results: ExperimentResults) -> ExperimentSummary:
    """Build aggregate and per-scenario measurements from recorded trials."""
    overall = _Counts()
    for trial in results.trials:
        overall.include(trial)
    scenarios = [
        _scenario_summary(
            case_id,
            [trial for trial in results.trials if trial.case_id == case_id],
        )
        for case_id in dict.fromkeys(trial.case_id for trial in results.trials)
    ]
    return ExperimentSummary(
        name=results.name,
        trials=len(results.trials),
        completed=overall.completed,
        errors=overall.errors,
        fully_passed=overall.fully_passed,
        openai_passed=overall.openai_passed,
        openai_total=overall.openai_total,
        jev_passed=overall.jev_passed,
        jev_total=overall.jev_total,
        agreement=overall.agreement,
        agreement_total=overall.agreement_total,
        openai_pass_jev_pass=overall.openai_pass_jev_pass,
        openai_pass_jev_fail=overall.openai_pass_jev_fail,
        openai_fail_jev_pass=overall.openai_fail_jev_pass,
        openai_fail_jev_fail=overall.openai_fail_jev_fail,
        scenarios=scenarios,
    )


def _scenario_summary(case_id: str, trials: list[TrialResult]) -> ScenarioSummary:
    counts = _Counts()
    for trial in trials:
        counts.include(trial)
    durations = [trial.duration_seconds for trial in trials]
    return ScenarioSummary(
        case_id=case_id,
        name=next(
            (trial.case_name for trial in trials if trial.case_name is not None),
            case_id,
        ),
        trials=len(trials),
        completed=counts.completed,
        errors=counts.errors,
        fully_passed=counts.fully_passed,
        openai_passed=counts.openai_passed,
        openai_total=counts.openai_total,
        jev_passed=counts.jev_passed,
        jev_total=counts.jev_total,
        agreement=counts.agreement,
        agreement_total=counts.agreement_total,
        average_duration_seconds=(sum(durations) / len(durations) if durations else 0),
    )
