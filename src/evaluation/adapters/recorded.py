"""Import recorded responses without claiming the prompt caused them."""

from dataclasses import dataclass

from ..schemas import (
    Candidate,
    CandidateOutcome,
    CanonicalRequest,
    EvaluationDeclaration,
    RecordedResponse,
    Scenario,
    TrialArtifact,
    TrialLifecycle,
    ValidityStatus,
    digest_json,
    utc_now,
)


@dataclass(frozen=True)
class RecordedResponseRunner:
    declaration: EvaluationDeclaration
    responses: dict[tuple[str, str, int], RecordedResponse]

    def run(
        self,
        candidate: Candidate,
        scenario: Scenario,
        *,
        repetition: int,
        planned_order: int,
        actual_order: int,
    ) -> TrialArtifact:
        key = (candidate.candidate_id, scenario.scenario_id, repetition)
        try:
            recorded = self.responses[key]
        except KeyError as error:
            raise KeyError(f"missing recorded response for {key}") from error

        occurred_at = utc_now()
        trial_key = {
            "run_id": self.declaration.run_id,
            "scenario_id": scenario.scenario_id,
            "candidate_id": candidate.candidate_id,
            "repetition": repetition,
        }
        raw_items = recorded.raw_response_items or (
            {
                "type": "message",
                "role": "assistant",
                "content": recorded.projected_response,
            },
        )
        return TrialArtifact(
            trial_id=f"trial-{digest_json(trial_key)[:24]}",
            run_id=self.declaration.run_id,
            candidate_id=candidate.candidate_id,
            scenario_id=scenario.scenario_id,
            source_family_id=scenario.source_family_id,
            repetition=repetition,
            planned_order=planned_order,
            actual_order=actual_order,
            execution_protocol="recorded-v1",
            causal_source="recorded",
            request=CanonicalRequest(
                instructions=candidate.resolved_prompt,
                history=scenario.model_visible_history,
                configuration=candidate.configuration,
            ),
            raw_response_items=raw_items,
            projected_response=recorded.projected_response,
            started_at=occurred_at,
            completed_at=occurred_at,
            lifecycle=TrialLifecycle.SUCCEEDED,
            validity=ValidityStatus.VALID,
            outcome=CandidateOutcome.RESPONSE,
            adapter_id=self.declaration.adapter_id,
            code_revision=self.declaration.code_revision,
            response_provenance=recorded.provenance,
            sensitivity=recorded.sensitivity,
        )
