"""Replaceable boundaries for candidate execution and grading."""

from typing import Protocol

from .schemas import Candidate, Observation, Scenario, TrialArtifact


class CandidateRunner(Protocol):
    def run(
        self,
        candidate: Candidate,
        scenario: Scenario,
        *,
        repetition: int,
        planned_order: int,
        actual_order: int,
    ) -> TrialArtifact: ...


class Grader(Protocol):
    def grade(self, trial: TrialArtifact) -> Observation: ...
