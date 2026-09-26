"""Versioned data contracts for the experimental prompt evaluator."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    model_validator,
)


SCHEMA_VERSION = "1.0"
Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
ObservationScalar = StrictBool | StrictInt | StrictFloat | str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    """Serialize evidence consistently for hashing and persistence."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=False)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest_json(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class Partition(StrEnum):
    DEVELOPMENT = "development"
    QUALIFICATION = "qualification"
    VALIDATION = "validation"


class GraderKind(StrEnum):
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"
    HUMAN = "human"


class ObservationStatus(StrEnum):
    OBSERVED = "observed"
    ABSTAINED = "abstained"
    NOT_APPLICABLE = "not_applicable"
    MISSING_EVIDENCE = "missing_evidence"
    GRADER_ERROR = "grader_error"


class ValueType(StrEnum):
    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    NUMERIC = "numeric"
    QUALITATIVE = "qualitative"


class TrialLifecycle(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INVALID = "invalid"


class RunLifecycle(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PREPARED = "prepared"
    RUNNING = "running"
    EXECUTED = "executed"
    GRADING = "grading"
    GRADED = "graded"
    ANALYZED = "analyzed"
    REPORTED = "reported"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidityStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    EXCLUDED = "excluded"


class CandidateOutcome(StrEnum):
    RESPONSE = "response"
    TOOL_REQUEST = "tool_request"
    CONVERSATION_COMPLETION = "conversation_completion"
    NO_OUTPUT = "no_output"


class FailureStage(StrEnum):
    SETUP = "setup"
    ADAPTER = "adapter"
    PROVIDER = "provider"
    PARSER = "parser"
    TOOL = "tool"
    DRIVER = "driver"
    TRANSPORT = "transport"
    STORAGE = "storage"
    GRADER = "grader"
    HUMAN_REVIEW = "human_review"


class ComparisonDecision(StrEnum):
    BETTER = "better"
    NOT_WORSE = "not_worse"
    WORSE = "worse"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"


class ScenarioMessage(StrictModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str = Field(min_length=1)


class AgentConfiguration(StrictModel):
    model: str = Field(min_length=1)
    reasoning: str | None = None
    tools: tuple[str, ...] = ()
    tool_choice: str = "none"
    output_contract: dict[str, Any] | None = None


class Candidate(StrictModel):
    candidate_id: Identifier
    label: str = Field(min_length=1)
    resolved_prompt: str = Field(min_length=1)
    prompt_source_digests: dict[Identifier, Digest] = Field(default_factory=dict)
    configuration: AgentConfiguration
    prompt_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_prompt_digest(self) -> "Candidate":
        expected = digest_text(self.resolved_prompt)
        if self.prompt_digest is not None and self.prompt_digest != expected:
            raise ValueError("candidate prompt digest does not match resolved prompt")
        object.__setattr__(self, "prompt_digest", expected)
        return self


class Scenario(StrictModel):
    scenario_id: Identifier
    version: Annotated[str, StringConstraints(min_length=1, max_length=64)] = "1"
    model_visible_history: tuple[ScenarioMessage, ...] = Field(min_length=1)
    reference_material: str | None = None
    learner_state: str = Field(min_length=1)
    permitted_help: str = Field(min_length=1)
    applicable_criteria: tuple[Identifier, ...] = Field(min_length=1)
    source_family_id: Identifier
    partition: Partition = Partition.DEVELOPMENT
    slices: dict[Identifier, str] = Field(default_factory=dict)
    provenance: str = Field(min_length=1)
    privacy_manifest_id: Identifier
    sensitivity: Sensitivity = Sensitivity.PUBLIC


class CriterionDefinition(StrictModel):
    criterion_id: Identifier
    name: str = Field(min_length=1)
    value_type: ValueType
    ordered_values: tuple[str, ...] = ()
    primary: bool = False
    guardrail: bool = False

    @model_validator(mode="after")
    def validate_scale(self) -> "CriterionDefinition":
        if self.value_type == ValueType.ORDINAL and len(self.ordered_values) < 2:
            raise ValueError("ordinal criteria require at least two ordered values")
        if self.value_type != ValueType.ORDINAL and self.ordered_values:
            raise ValueError("ordered_values are only valid for ordinal criteria")
        if len(set(self.ordered_values)) != len(self.ordered_values):
            raise ValueError("ordered_values must be unique")
        return self


class GraderDefinition(StrictModel):
    grader_id: Identifier
    version: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    kind: GraderKind
    criterion_ids: tuple[Identifier, ...] = Field(min_length=1)


class RunPolicy(StrictModel):
    repetitions: int = Field(default=1, ge=1, le=100)
    random_seed: int = 0
    max_candidate_calls: int = Field(default=0, ge=0)
    max_grader_calls: int = Field(default=0, ge=0)
    max_cost_usd: float | None = Field(default=None, gt=0)
    retry_limit: int = Field(default=0, ge=0, le=10)


class EvaluationDeclaration(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    run_id: Identifier
    question: str = Field(min_length=1)
    claim_type: Literal["prompt_comparison"] = "prompt_comparison"
    exploratory: bool = True
    candidates: tuple[Candidate, Candidate]
    scenarios: tuple[Scenario, ...] = Field(min_length=1)
    criteria: tuple[CriterionDefinition, ...] = Field(min_length=1)
    graders: tuple[GraderDefinition, ...] = Field(default_factory=tuple)
    policy: RunPolicy = Field(default_factory=RunPolicy)
    privacy_manifest_id: Identifier
    code_revision: str = Field(min_length=1)
    dependency_lock_digest: Digest
    adapter_id: Identifier

    @model_validator(mode="after")
    def validate_declaration(self) -> "EvaluationDeclaration":
        candidate_ids = [item.candidate_id for item in self.candidates]
        scenario_ids = [item.scenario_id for item in self.scenarios]
        criterion_ids = [item.criterion_id for item in self.criteria]
        grader_ids = [item.grader_id for item in self.graders]
        for name, values in (
            ("candidate", candidate_ids),
            ("scenario", scenario_ids),
            ("criterion", criterion_ids),
            ("grader", grader_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} IDs must be unique")

        fixed_configuration = self.candidates[0].configuration
        if any(
            candidate.configuration != fixed_configuration
            for candidate in self.candidates[1:]
        ):
            raise ValueError(
                "prompt comparison candidates must have identical non-prompt configuration"
            )

        if not any(criterion.primary for criterion in self.criteria):
            raise ValueError("at least one criterion must be marked primary")

        known_criteria = set(criterion_ids)
        for scenario in self.scenarios:
            unknown = set(scenario.applicable_criteria) - known_criteria
            if unknown:
                raise ValueError(
                    f"scenario {scenario.scenario_id} has unknown criteria: "
                    f"{sorted(unknown)}"
                )
        for grader in self.graders:
            unknown = set(grader.criterion_ids) - known_criteria
            if unknown:
                raise ValueError(
                    f"grader {grader.grader_id} has unknown criteria: {sorted(unknown)}"
                )
        return self


class CanonicalRequest(StrictModel):
    instructions: str = Field(min_length=1)
    history: tuple[ScenarioMessage, ...] = Field(min_length=1)
    configuration: AgentConfiguration
    request_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_request_digest(self) -> "CanonicalRequest":
        expected = digest_json(
            {
                "instructions": self.instructions,
                "history": [item.model_dump(mode="json") for item in self.history],
                "configuration": self.configuration.model_dump(mode="json"),
            }
        )
        if self.request_digest is not None and self.request_digest != expected:
            raise ValueError("request digest does not match request content")
        object.__setattr__(self, "request_digest", expected)
        return self


class Usage(StrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class RetryEvent(StrictModel):
    attempt: int = Field(ge=1)
    reason: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=utc_now)


class Failure(StrictModel):
    stage: FailureStage
    code: Identifier
    message: str = Field(min_length=1)


class RecordedResponse(StrictModel):
    projected_response: str = Field(min_length=1)
    raw_response_items: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    provenance: str = Field(min_length=1)
    sensitivity: Sensitivity = Sensitivity.PUBLIC


class OfflineRecordedCase(StrictModel):
    candidate_id: Identifier
    scenario_id: Identifier
    repetition: int = Field(ge=1)
    response: RecordedResponse
    ratings: dict[Identifier, str]


class OfflineFixture(StrictModel):
    declaration: EvaluationDeclaration
    cases: tuple[OfflineRecordedCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_cases(self) -> "OfflineFixture":
        candidates = {item.candidate_id for item in self.declaration.candidates}
        scenarios = {item.scenario_id: item for item in self.declaration.scenarios}
        criteria = {
            item.criterion_id: item for item in self.declaration.criteria
        }
        seen: set[tuple[str, str, int]] = set()
        for case in self.cases:
            key = (case.candidate_id, case.scenario_id, case.repetition)
            if key in seen:
                raise ValueError(f"duplicate recorded case: {key}")
            seen.add(key)
            if case.candidate_id not in candidates:
                raise ValueError(f"unknown case candidate: {case.candidate_id}")
            if case.scenario_id not in scenarios:
                raise ValueError(f"unknown case scenario: {case.scenario_id}")
            if case.repetition > self.declaration.policy.repetitions:
                raise ValueError(f"case repetition exceeds run policy: {key}")
            expected_ratings = set(scenarios[case.scenario_id].applicable_criteria)
            if set(case.ratings) != expected_ratings:
                raise ValueError(
                    f"case ratings for {key} must equal applicable criteria: "
                    f"{sorted(expected_ratings)}"
                )
            if not set(case.ratings).issubset(criteria):
                raise ValueError(f"case {key} uses an unknown criterion")
            for criterion_id, rating in case.ratings.items():
                criterion = criteria[criterion_id]
                if (
                    criterion.value_type == ValueType.ORDINAL
                    and rating not in criterion.ordered_values
                ):
                    raise ValueError(
                        f"case {key} rating {rating!r} is outside "
                        f"the {criterion_id} scale"
                    )

        expected_cases = {
            (candidate_id, scenario_id, repetition)
            for candidate_id in candidates
            for scenario_id in scenarios
            for repetition in range(1, self.declaration.policy.repetitions + 1)
        }
        missing = expected_cases - seen
        if missing:
            raise ValueError(f"fixture is missing recorded cases: {sorted(missing)}")
        return self


class TrialArtifact(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    trial_id: Identifier
    run_id: Identifier
    candidate_id: Identifier
    scenario_id: Identifier
    source_family_id: Identifier
    repetition: int = Field(ge=1)
    planned_order: int = Field(ge=1)
    actual_order: int = Field(ge=1)
    execution_protocol: Identifier
    causal_source: Literal["recorded", "generated"]
    request: CanonicalRequest
    raw_response_items: tuple[dict[str, Any], ...]
    projected_response: str | None = None
    usage: Usage | None = None
    retries: tuple[RetryEvent, ...] = ()
    started_at: datetime
    completed_at: datetime
    lifecycle: TrialLifecycle
    validity: ValidityStatus
    validity_reason: str | None = None
    outcome: CandidateOutcome
    failure: Failure | None = None
    adapter_id: Identifier
    code_revision: str = Field(min_length=1)
    response_provenance: str = Field(min_length=1)
    sensitivity: Sensitivity = Sensitivity.PUBLIC

    @model_validator(mode="after")
    def validate_status(self) -> "TrialArtifact":
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if self.lifecycle == TrialLifecycle.SUCCEEDED:
            if self.validity != ValidityStatus.VALID:
                raise ValueError("a succeeded trial must be valid")
            if self.outcome == CandidateOutcome.RESPONSE and not self.projected_response:
                raise ValueError("response outcome requires projected_response")
            if self.failure is not None:
                raise ValueError("a succeeded trial cannot contain failure")
        if self.lifecycle == TrialLifecycle.FAILED and self.failure is None:
            raise ValueError("a failed trial requires failure details")
        if self.validity != ValidityStatus.VALID and not self.validity_reason:
            raise ValueError("invalid or excluded trials require a reason")
        return self


class EvidenceReference(StrictModel):
    artifact_id: Identifier
    field_path: str = Field(min_length=1)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    quoted_text: str | None = None
    content_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_span(self) -> "EvidenceReference":
        span_values = (self.start, self.end, self.quoted_text, self.content_digest)
        if any(value is not None for value in span_values) and any(
            value is None for value in span_values
        ):
            raise ValueError("span references require start, end, quote, and digest")
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("evidence end cannot precede start")
        return self


class Observation(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    observation_id: Identifier
    run_id: Identifier
    trial_id: Identifier
    candidate_id: Identifier
    scenario_id: Identifier
    source_family_id: Identifier
    repetition: int = Field(ge=1)
    criterion_id: Identifier
    grader_id: Identifier
    grader_version: str = Field(min_length=1)
    value_type: ValueType
    value: ObservationScalar | None = None
    status: ObservationStatus
    evidence: tuple[EvidenceReference, ...] = ()
    rationale: str = ""
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_value(self) -> "Observation":
        if self.status == ObservationStatus.OBSERVED and self.value is None:
            raise ValueError("observed values cannot be missing")
        if self.status != ObservationStatus.OBSERVED and self.value is not None:
            raise ValueError("non-observed statuses cannot contain a value")
        if self.status == ObservationStatus.OBSERVED:
            if self.value_type == ValueType.BOOLEAN and type(self.value) is not bool:
                raise ValueError("boolean observation requires a boolean value")
            if self.value_type in {
                ValueType.CATEGORICAL,
                ValueType.ORDINAL,
                ValueType.QUALITATIVE,
            } and not isinstance(self.value, str):
                raise ValueError("text observation requires a string value")
            if self.value_type == ValueType.NUMERIC and (
                isinstance(self.value, bool)
                or not isinstance(self.value, (int, float))
            ):
                raise ValueError("numeric observation requires a number")
        return self


class PairedCriterionResult(StrictModel):
    criterion_id: Identifier
    candidate_a_id: Identifier
    candidate_b_id: Identifier
    expected_pairs: int = Field(ge=0)
    compared_pairs: int = Field(ge=0)
    candidate_a_better: int = Field(ge=0)
    candidate_b_better: int = Field(ge=0)
    ties: int = Field(ge=0)
    unavailable_pairs: int = Field(ge=0)
    candidate_a_unavailable: int = Field(ge=0)
    candidate_b_unavailable: int = Field(ge=0)


class ComparisonSummary(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    run_id: Identifier
    question: str
    candidate_a_id: Identifier
    candidate_b_id: Identifier
    decision: ComparisonDecision
    decision_reason: str
    exploratory: bool
    scenario_count: int = Field(ge=0)
    source_family_count: int = Field(ge=0)
    trial_count: int = Field(ge=0)
    results: tuple[PairedCriterionResult, ...]
    limitations: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)


class ArtifactEnvelope(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    artifact_id: Identifier
    artifact_type: Identifier
    created_at: datetime = Field(default_factory=utc_now)
    producer: Identifier
    sensitivity: Sensitivity
    payload_digest: Digest
    payload: dict[str, Any]
    parent_artifact_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_payload_digest(self) -> "ArtifactEnvelope":
        if digest_json(self.payload) != self.payload_digest:
            raise ValueError("artifact payload digest does not match payload")
        return self
