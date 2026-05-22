from dataclasses import dataclass, replace
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError


PRIORITY_KEYS = ["error_meaning", "error_location", "intended_behavior", "fix"]
PRIORITY_STATUS_VALUES = ["missing", "fulfilled", "incorrect", "incomplete"]

RUBRIC_ASSESSMENT_OUTPUT_FORMAT = {
    "format": {
        "type": "json_schema",
        "name": "debugging_practice_rubric_assessment",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reason for evaluations": {
                    "type": "string",
                    "description": "Brief reasoning for the assessment values.",
                },
                "latest_attempted_priority": {
                    "anyOf": [
                        {
                            "type": "string",
                            "enum": PRIORITY_KEYS,
                        },
                        {
                            "type": "null",
                        },
                    ],
                    "description": (
                        "The one priority topic the latest TA response was attempting. "
                        "Use null when the latest response did not attempt any priority topic, "
                        "including direct requests for the answer, solution, fix, code, or exact change."
                    ),
                },
                "latest_attempted_status": {
                    "type": "string",
                    "enum": PRIORITY_STATUS_VALUES,
                    "description": (
                        "The status of the latest attempted priority: missing, fulfilled, incorrect, or incomplete. "
                        "Use missing when latest_attempted_priority is null, including direct-answer requests."
                    ),
                },
                "fulfilled_priorities": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": PRIORITY_KEYS,
                    },
                    "description": (
                        "All priority topics that are correctly satisfied anywhere in the full conversation "
                        "for the current rubric item. The workflow centrally merges this observation with "
                        "previous progress and does not let absent items clear fulfilled state."
                    ),
                },
                "unrelated": {
                    "type": "boolean",
                    "description": (
                        "True for direct requests for the answer, solution, fix, code, exact change, "
                        "or final result, and for clearly off-topic responses."
                    ),
                },
            },
            "required": [
                "reason for evaluations",
                "latest_attempted_priority",
                "latest_attempted_status",
                "fulfilled_priorities",
                "unrelated",
            ],
            "additionalProperties": False,
        },
    }
}

TA_INCOMPLETE_OUTPUT_FORMAT = {
    "format": {
        "type": "json_schema",
        "name": "debugging_practice_ta_incomplete",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string"},
                "incomplete_response_part": {"type": "string"},
                "student_response": {"type": "string"},
            },
            "required": ["reasoning", "incomplete_response_part", "student_response"],
            "additionalProperties": False,
        },
    }
}

UNRELATED_COMPLETION_OUTPUT_FORMAT = {
    "format": {
        "type": "json_schema",
        "name": "debugging_practice_unrelated_completion",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string"},
                "response": {"type": "string"},
            },
            "required": ["reasoning", "response"],
            "additionalProperties": False,
        },
    }
}

CONCEPT_TRANSFER_OUTPUT_FORMAT = {
    "format": {
        "type": "json_schema",
        "name": "debugging_practice_concept_transfer",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string"},
                "concept_understood": {"type": "boolean"},
                "response": {"type": "string"},
            },
            "required": ["reasoning", "concept_understood", "response"],
            "additionalProperties": False,
        },
    }
}


@dataclass(frozen=True)
class PriorityState:
    fulfilled: bool
    latest_attempted: bool
    status: str


@dataclass(frozen=True)
class PriorityObservation:
    fulfilled_priorities: list[str]
    latest_attempted_priority: str | None
    latest_attempted_status: str
    unrelated: bool = False
    reason_for_evaluations: str = ""


@dataclass(frozen=True)
class RubricAssessment:
    rubric_finished: bool
    rubric_item_fulfilled: bool
    next_rubric_item: str | None
    latest_attempted_priority: str | None
    priorities: dict[str, PriorityState]
    unrelated: bool = False
    reason_for_evaluations: str = ""


@dataclass(frozen=True)
class TAIncompleteDecision:
    reasoning: str
    incomplete_response_part: str
    student_response: str


@dataclass(frozen=True)
class UnrelatedCompletion:
    reasoning: str
    response: str


@dataclass(frozen=True)
class ConceptTransferCompletion:
    reasoning: str
    concept_understood: bool
    response: str


class RubricAssessmentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason_for_evaluations: str = Field(default="", alias="reason for evaluations")
    latest_attempted_priority: str | None = None
    latest_attempted_status: str = "missing"
    fulfilled_priorities: list[str] = Field(default_factory=list)
    unrelated: bool = False


class TAIncompleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    incomplete_response_part: str
    student_response: str


class UnrelatedCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    response: str


class ConceptTransferResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    concept_understood: bool
    response: str


class ValidationSchema:
    priority_keys = PRIORITY_KEYS
    priority_status_values = PRIORITY_STATUS_VALUES
    rubric_assessment_output_format = RUBRIC_ASSESSMENT_OUTPUT_FORMAT
    ta_incomplete_output_format = TA_INCOMPLETE_OUTPUT_FORMAT
    unrelated_completion_output_format = UNRELATED_COMPLETION_OUTPUT_FORMAT
    concept_transfer_output_format = CONCEPT_TRANSFER_OUTPUT_FORMAT

    @staticmethod
    def _empty_priorities(current_priorities: dict[str, bool] | None = None) -> dict[str, PriorityState]:
        current_priorities = current_priorities or {}
        return {
            priority_key: PriorityState(
                fulfilled=bool(current_priorities.get(priority_key, False)),
                latest_attempted=False,
                status="fulfilled" if current_priorities.get(priority_key, False) else "missing",
            )
            for priority_key in PRIORITY_KEYS
        }

    @staticmethod
    def _normalize_priority_status(value: str | None) -> str:
        if value in PRIORITY_STATUS_VALUES:
            return value
        return "missing"

    @staticmethod
    def _normalize_priority_key(value: str | None) -> str | None:
        if value in PRIORITY_KEYS:
            return value
        return None

    @staticmethod
    def _unwrap_json_markdown(raw_response: str) -> str:
        raw_response = raw_response.strip()
        if raw_response.startswith("```"):
            raw_response = raw_response.strip("`").strip()
            if raw_response.startswith("json"):
                raw_response = raw_response[4:].strip()
        return raw_response

    @staticmethod
    def _observation_with_fix_implications(
            observation: PriorityObservation,
            current_required_fix: str,
    ) -> PriorityObservation:
        if (
                observation.unrelated
                or observation.latest_attempted_priority != "fix"
                or observation.latest_attempted_status != "fulfilled"
                or not current_required_fix.strip()
        ):
            return observation

        fulfilled_priorities = list(dict.fromkeys([
            *observation.fulfilled_priorities,
            "fix",
            "error_location",
            "intended_behavior",
        ]))
        return replace(observation, fulfilled_priorities=fulfilled_priorities)

    @classmethod
    def _assessment_from_progress(
            cls,
            priorities: dict[str, PriorityState],
            observation: PriorityObservation,
            next_scenario_name: str | None,
    ) -> RubricAssessment:
        item_fulfilled = all(
            priority.fulfilled and priority.status == "fulfilled"
            for priority in priorities.values()
        )
        rubric_finished = item_fulfilled and next_scenario_name is None
        return RubricAssessment(
            rubric_finished=rubric_finished,
            rubric_item_fulfilled=item_fulfilled,
            next_rubric_item=next_scenario_name if item_fulfilled else None,
            latest_attempted_priority=observation.latest_attempted_priority,
            priorities=priorities,
            unrelated=observation.unrelated,
            reason_for_evaluations=observation.reason_for_evaluations,
        )

    @classmethod
    def parse_assessment(
            cls,
            raw_response: str | None,
            current_priorities: dict[str, bool] | None = None,
            next_scenario_name: str | None = None,
            current_required_fix: str = "",
    ) -> RubricAssessment:
        priorities = cls._empty_priorities(current_priorities)
        if not raw_response:
            return cls._assessment_from_progress(
                priorities,
                PriorityObservation([], None, "missing"),
                next_scenario_name,
            )

        raw_response = cls._unwrap_json_markdown(raw_response)

        try:
            payload = RubricAssessmentResponse.model_validate_json(raw_response)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return cls._assessment_from_progress(
                priorities,
                PriorityObservation([], None, "missing"),
                next_scenario_name,
            )

        latest_attempted_priority = cls._normalize_priority_key(payload.latest_attempted_priority)
        latest_attempted_status = cls._normalize_priority_status(payload.latest_attempted_status)
        fulfilled_priorities = [
            priority_key
            for priority_key in payload.fulfilled_priorities
            if priority_key in PRIORITY_KEYS
        ]
        observation = PriorityObservation(
            fulfilled_priorities=fulfilled_priorities,
            latest_attempted_priority=latest_attempted_priority,
            latest_attempted_status=latest_attempted_status,
            unrelated=payload.unrelated,
            reason_for_evaluations=payload.reason_for_evaluations,
        )
        observation = cls._observation_with_fix_implications(observation, current_required_fix)

        for priority_key in observation.fulfilled_priorities:
            if priority_key not in priorities:
                continue
            priorities[priority_key] = PriorityState(
                fulfilled=True,
                latest_attempted=False,
                status="fulfilled",
            )

        if latest_attempted_priority in priorities:
            current = priorities[latest_attempted_priority]
            fulfilled = current.fulfilled or latest_attempted_status == "fulfilled"
            priorities[latest_attempted_priority] = PriorityState(
                fulfilled=fulfilled,
                latest_attempted=True,
                status="fulfilled" if fulfilled else latest_attempted_status,
            )

        return cls._assessment_from_progress(priorities, observation, next_scenario_name)

    @classmethod
    def parse_ta_incomplete_response(cls, raw_response: str | None) -> TAIncompleteDecision:
        if not raw_response:
            return TAIncompleteDecision(reasoning="", incomplete_response_part="", student_response="")

        raw_response = cls._unwrap_json_markdown(raw_response)
        try:
            payload = TAIncompleteResponse.model_validate_json(raw_response)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return TAIncompleteDecision(reasoning="", incomplete_response_part="", student_response="")

        return TAIncompleteDecision(
            reasoning=payload.reasoning,
            incomplete_response_part=payload.incomplete_response_part,
            student_response=payload.student_response,
        )

    @classmethod
    def parse_unrelated_completion(cls, raw_response: str | None) -> UnrelatedCompletion:
        if not raw_response:
            return UnrelatedCompletion(reasoning="", response="")

        raw_response = cls._unwrap_json_markdown(raw_response)
        try:
            payload = UnrelatedCompletionResponse.model_validate_json(raw_response)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return UnrelatedCompletion(reasoning="", response="")

        return UnrelatedCompletion(reasoning=payload.reasoning, response=payload.response)

    @classmethod
    def parse_concept_transfer(cls, raw_response: str | None) -> ConceptTransferCompletion:
        if not raw_response:
            return ConceptTransferCompletion(reasoning="", concept_understood=False, response="")

        raw_response = cls._unwrap_json_markdown(raw_response)
        try:
            payload = ConceptTransferResponse.model_validate_json(raw_response)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return ConceptTransferCompletion(reasoning="", concept_understood=False, response="")

        return ConceptTransferCompletion(
            reasoning=payload.reasoning,
            concept_understood=payload.concept_understood,
            response=payload.response,
        )
