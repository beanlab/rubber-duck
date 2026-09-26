"""Deterministic graders for evidence integrity."""

from __future__ import annotations

from .schemas import (
    EvidenceReference,
    EvaluationDeclaration,
    Observation,
    ObservationStatus,
    TrialArtifact,
    TrialLifecycle,
    ValidityStatus,
    ValueType,
    digest_text,
)


class EvidenceIntegrityGrader:
    grader_id = "evidence-integrity"
    version = "1"
    criterion_id = "evidence_integrity"

    def __init__(self, declaration: EvaluationDeclaration):
        self.declaration = declaration

    def grade(self, trial: TrialArtifact) -> Observation:
        problems: list[str] = []
        candidates = {
            candidate.candidate_id: candidate
            for candidate in self.declaration.candidates
        }
        scenarios = {
            scenario.scenario_id: scenario
            for scenario in self.declaration.scenarios
        }
        candidate = candidates.get(trial.candidate_id)
        scenario = scenarios.get(trial.scenario_id)
        if trial.run_id != self.declaration.run_id:
            problems.append("trial belongs to a different run")
        if candidate is None:
            problems.append("candidate is not declared")
        else:
            if trial.request.instructions != candidate.resolved_prompt:
                problems.append("request instructions differ from resolved prompt")
            if trial.request.configuration != candidate.configuration:
                problems.append("request configuration differs from candidate")
        if scenario is None:
            problems.append("scenario is not declared")
        else:
            if trial.request.history != scenario.model_visible_history:
                problems.append("request history differs from scenario")
            if trial.source_family_id != scenario.source_family_id:
                problems.append("trial source family differs from scenario")
        if trial.adapter_id != self.declaration.adapter_id:
            problems.append("trial adapter differs from declaration")
        if trial.code_revision != self.declaration.code_revision:
            problems.append("trial code revision differs from declaration")
        if trial.lifecycle != TrialLifecycle.SUCCEEDED:
            problems.append(f"trial lifecycle is {trial.lifecycle}")
        if trial.validity != ValidityStatus.VALID:
            problems.append(f"trial validity is {trial.validity}")
        if not trial.projected_response:
            problems.append("projected response is missing")
        if not trial.raw_response_items:
            problems.append("raw response items are missing")

        if trial.projected_response:
            response = trial.projected_response
            evidence = (
                EvidenceReference(
                    artifact_id=trial.trial_id,
                    field_path="projected_response",
                    start=0,
                    end=len(response),
                    quoted_text=response,
                    content_digest=digest_text(response),
                ),
            )
        else:
            evidence = ()

        passed = not problems
        rationale = (
            "Required response evidence is present."
            if passed
            else "; ".join(problems)
        )
        return Observation(
            observation_id=f"{trial.trial_id}.integrity",
            run_id=trial.run_id,
            trial_id=trial.trial_id,
            candidate_id=trial.candidate_id,
            scenario_id=trial.scenario_id,
            source_family_id=trial.source_family_id,
            repetition=trial.repetition,
            criterion_id=self.criterion_id,
            grader_id=self.grader_id,
            grader_version=self.version,
            value_type=ValueType.BOOLEAN,
            value=passed,
            status=ObservationStatus.OBSERVED,
            evidence=evidence,
            rationale=rationale,
        )


def validate_evidence_span(trial: TrialArtifact, reference: EvidenceReference) -> bool:
    """Verify the initial exact-span citation format against a trial."""
    if reference.artifact_id != trial.trial_id:
        return False
    if reference.field_path != "projected_response":
        return False
    if trial.projected_response is None or reference.start is None or reference.end is None:
        return False
    quoted = trial.projected_response[reference.start : reference.end]
    return (
        quoted == reference.quoted_text
        and digest_text(quoted) == reference.content_digest
    )
