import json
import random
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from quest import step
import yaml

from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DebuggingPracticeDuckSettings, DuckContext
from ..utils.message_utils import wait_for_message
from ..utils.protocols import ConversationComplete


ConversationTurn = tuple[str, str]
PROMPT_DIRECTORY = Path(__file__).parents[2] / "prompts" / "debugging-practice-duck"
PREFAB_RESPONSES_PATH = PROMPT_DIRECTORY / "prefabs.yaml"
EVAL_STEP_PROMPT_PATH = PROMPT_DIRECTORY / "eval-step.md"
TA_INCOMPLETE_PROMPT_PATH = PROMPT_DIRECTORY / "TA-incomplete.md"
UNRELATED_COMPLETIONS_PROMPT_PATH = PROMPT_DIRECTORY / "unrelated-completions.md"
CONCEPT_TRANSFER_PROMPT_PATH = PROMPT_DIRECTORY / "concept-transfer.md"
INCOMPLETE_PROMPTS_BEFORE_CONCEPT_TRANSFER = 1
DEBUGGING_PRACTICE_FEEDBACK_MESSAGE = (
    "*The debugging practice duck is an experimental feature that is actively being developed. "
    "Please leave feedback as to your experience using the duck.*"
)


@dataclass(frozen=True)
class RubricScenario:
    name: str
    rubric_item: str
    error: str
    code: str
    error_line: str
    intended_behavior: str
    required_fix: str
    required_concept: str


@dataclass(frozen=True)
class PriorityAssessment:
    fulfilled: bool
    latest_attempted: bool
    status: str


@dataclass(frozen=True)
class RubricAssessment:
    rubric_finished: bool
    rubric_item_fulfilled: bool
    next_rubric_item: str | None
    latest_attempted_priority: str | None
    priorities: dict[str, PriorityAssessment]
    unrelated: bool = False
    reason_for_evaluations: str = ""


@dataclass(frozen=True)
class PriorityObservation:
    fulfilled_priorities: list[str]
    latest_attempted_priority: str | None
    latest_attempted_status: str
    unrelated: bool = False
    reason_for_evaluations: str = ""


@dataclass(frozen=True)
class PriorityProgress:
    priorities: dict[str, PriorityAssessment]

    @classmethod
    def empty(cls) -> "PriorityProgress":
        return cls({
            priority_item.key: PriorityAssessment(
                fulfilled=False,
                latest_attempted=False,
                status="missing",
            )
            for priority_item in PRIORITY_ITEMS
        })

    def apply(self, observation: PriorityObservation) -> "PriorityProgress":
        priorities = {
            key: PriorityAssessment(
                fulfilled=priority.fulfilled,
                latest_attempted=False,
                status="fulfilled" if priority.fulfilled else "missing",
            )
            for key, priority in self.priorities.items()
        }

        for priority_key in observation.fulfilled_priorities:
            if priority_key not in priorities:
                continue
            priorities[priority_key] = PriorityAssessment(
                fulfilled=True,
                latest_attempted=False,
                status="fulfilled",
            )

        latest_priority = observation.latest_attempted_priority
        if latest_priority in priorities:
            current = priorities[latest_priority]
            latest_status = observation.latest_attempted_status
            fulfilled = current.fulfilled or latest_status == "fulfilled"
            priorities[latest_priority] = PriorityAssessment(
                fulfilled=fulfilled,
                latest_attempted=True,
                status="fulfilled" if fulfilled else latest_status,
            )

        return PriorityProgress(priorities)


class RubricAssessmentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason_for_evaluations: str = Field(default="", alias="reason for evaluations")
    latest_attempted_priority: str | None = None
    latest_attempted_status: str = "missing"
    fulfilled_priorities: list[str] = Field(default_factory=list)
    unrelated: bool = False


@dataclass(frozen=True)
class PriorityItem:
    key: str
    label: str
    prefab_bucket: str


@dataclass(frozen=True)
class TAIncompleteDecision:
    reasoning: str
    incomplete_response_part: str
    student_response: str


class TAIncompleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    incomplete_response_part: str
    student_response: str


@dataclass(frozen=True)
class UnrelatedCompletion:
    reasoning: str
    response: str


class UnrelatedCompletionResponse(BaseModel):
    reasoning: str
    response: str


@dataclass(frozen=True)
class ConceptTransferCompletion:
    reasoning: str
    concept_understood: bool
    response: str


class ConceptTransferResponse(BaseModel):
    reasoning: str
    concept_understood: bool
    response: str


@dataclass(frozen=True)
class NextMessage:
    response: str
    is_finished: bool
    scenario_index: int
    transfer_priority: PriorityItem | None = None
    incomplete_priority: PriorityItem | None = None


PRIORITY_ITEMS = [
    PriorityItem("error_meaning", "what the error means", "ask_error_meaning"),
    PriorityItem("error_location", "where the error is located", "ask_error_location"),
    PriorityItem("intended_behavior", "what the code is trying to do", "ask_intended_behavior"),
    PriorityItem("fix", "what change needs to be made", "ask_for_fix"),
]

PRIORITY_STATUS_VALUES = ["missing", "fulfilled", "incorrect", "incomplete"]
PRIORITY_KEYS = [priority_item.key for priority_item in PRIORITY_ITEMS]


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
        "name": "incomplete_subprocess",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Brief third-party reasoning about why the response is incomplete.",
                },
                "incomplete_response_part": {
                    "type": "string",
                    "description": "The specific portion of the TA response that is incomplete.",
                },
                "student_response": {
                    "type": "string",
                    "description": (
                        "A concise student-facing response that says the identified part is incomplete "
                        "without giving the missing detail."
                    ),
                },
            },
            "required": [
                "reasoning",
                "incomplete_response_part",
                "student_response",
            ],
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
                "reasoning": {
                    "type": "string",
                    "description": "Brief third-party reasoning about why the response is unrelated.",
                },
                "response": {
                    "type": "string",
                    "description": "A student-style response from someone who knows nothing.",
                },
            },
            "required": ["reasoning", "response"],
            "additionalProperties": False,
        },
    }
}


CONCEPT_TRANSFER_OUTPUT_FORMAT = {
    "format": {
        "type": "json_schema",
        "name": "incorrect_subprocess",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Brief third-party reasoning for the concept-support response.",
                },
                "concept_understood": {
                    "type": "boolean",
                    "description": (
                        "True when the latest student response explicitly says they understand "
                        "or demonstrates understanding of the transfer concept."
                    ),
                },
                "response": {
                    "type": "string",
                    "description": "A concise student-facing concept-support response.",
                },
            },
            "required": ["reasoning", "concept_understood", "response"],
            "additionalProperties": False,
        },
    }
}


def _load_debugging_practice_responses() -> dict[str, list[str]]:
    with PREFAB_RESPONSES_PATH.open(encoding="utf-8") as prefab_file:
        responses = yaml.safe_load(prefab_file) or {}
    return {
        key: value
        for key, value in responses.items()
        if isinstance(value, list)
    }


DEBUGGING_PRACTICE_RESPONSES = _load_debugging_practice_responses()


def _configure_rubric_assessment_agent(agent: Agent) -> None:
    agent.prompt = EVAL_STEP_PROMPT_PATH.read_text(encoding="utf-8")
    agent.output_format = RUBRIC_ASSESSMENT_OUTPUT_FORMAT


def _review_turns(settings: dict[str, Any]):
    review_turns = settings.get("review_turns", 5)
    if review_turns == "full":
        return iter(int, 1)
    return range(review_turns)


class DebuggingPracticeDuckWorkflow:
    def __init__(
            self,
            name: str,
            send_message,
            settings: DebuggingPracticeDuckSettings,
            conversation_review_agent: Agent,
            ai_client: AIClient,
            incomplete_subprocess: Agent | None = None,
            incorrect_subprocess: Agent | None = None,
    ):
        self.name = name
        self._send_message = step(send_message)
        self._settings = settings
        self._conversation_review_agent = conversation_review_agent
        self._ai_client = ai_client
        _configure_rubric_assessment_agent(self._conversation_review_agent)
        self._ta_incomplete_agent = self._process_agent(
            incomplete_subprocess,
            "incomplete_subprocess",
            TA_INCOMPLETE_PROMPT_PATH,
            TA_INCOMPLETE_OUTPUT_FORMAT,
        )
        self._unrelated_completion_agent = self._process_agent(
            None,
            "debugging_practice_unrelated_completion",
            UNRELATED_COMPLETIONS_PROMPT_PATH,
            UNRELATED_COMPLETION_OUTPUT_FORMAT,
        )
        self._concept_transfer_agent = self._process_agent(
            incorrect_subprocess,
            "incorrect_subprocess",
            CONCEPT_TRANSFER_PROMPT_PATH,
            CONCEPT_TRANSFER_OUTPUT_FORMAT,
        )

    def _process_agent(
            self,
            configured_agent: Agent | None,
            default_name: str,
            prompt_path: Path,
            output_format: dict[str, Any],
    ) -> Agent:
        prompt = prompt_path.read_text(encoding="utf-8")
        if configured_agent:
            configured_agent.prompt = prompt
            configured_agent.output_format = output_format
            return configured_agent

        return Agent(
            name=default_name,
            prompt=prompt,
            model=self._conversation_review_agent.model,
            tools=[],
            tool_settings="none",
            output_format=output_format,
            reasoning=self._conversation_review_agent.reasoning,
        )

    async def __call__(self, context: DuckContext):
        try:
            conversation_context: list[ConversationTurn] = []
            rubric = await self._load_rubric()
            full_project = self._full_project(rubric)
            scenarios = self._rubric_scenarios(rubric)
            current_scenario_index = 0
            priority_progress = PriorityProgress.empty()
            active_transfer_priority: PriorityItem | None = None
            active_incomplete_priority: PriorityItem | None = None
            active_incomplete_prompt_count = 0

            opening_message = self._opening_message(rubric, full_project, scenarios)
            conversation_context.append(("Student", opening_message))
            await self._send_message(context.thread_id, opening_message)
            user_response = await self._wait_for_user_response(context)

            for _ in _review_turns(self._settings):
                conversation_context.append(("TA", user_response))

                assessment = await self._review_conversation(
                    context,
                    rubric,
                    full_project,
                    scenarios,
                    current_scenario_index,
                    conversation_context,
                    priority_progress,
                )
                priority_progress = PriorityProgress(assessment.priorities)

                if active_transfer_priority and not self._priority_item_understood(
                    assessment,
                    active_transfer_priority,
                ):
                    completion = await self._review_concept_transfer(
                        context,
                        scenarios,
                        current_scenario_index,
                        active_transfer_priority,
                        conversation_context,
                    )
                    if completion.concept_understood:
                        assessment = self._assessment_with_understood_priority(
                            assessment,
                            active_transfer_priority,
                        )
                        next_message = await self._next_message(
                            context,
                            rubric,
                            full_project,
                            assessment,
                            scenarios,
                            current_scenario_index,
                            conversation_context,
                        )
                    else:
                        next_message = NextMessage(
                            completion.response,
                            False,
                            current_scenario_index,
                            active_transfer_priority,
                        )
                elif active_incomplete_priority and not self._priority_item_understood(
                    assessment,
                    active_incomplete_priority,
                ):
                    next_message = await self._next_incomplete_subprocess_message(
                        context,
                        rubric,
                        full_project,
                        assessment,
                        scenarios,
                        current_scenario_index,
                        conversation_context,
                        active_incomplete_priority,
                        active_incomplete_prompt_count,
                    )
                else:
                    next_message = await self._next_message(
                        context,
                        rubric,
                        full_project,
                        assessment,
                        scenarios,
                        current_scenario_index,
                        conversation_context,
                    )

                priority_progress = PriorityProgress(assessment.priorities)

                if not next_message.response:
                    return

                conversation_context.append(("Student", next_message.response))
                await self._send_message(context.thread_id, next_message.response)
                if next_message.is_finished:
                    await self._send_message(context.thread_id, DEBUGGING_PRACTICE_FEEDBACK_MESSAGE)
                    return

                previous_scenario_index = current_scenario_index
                current_scenario_index = next_message.scenario_index
                if current_scenario_index != previous_scenario_index:
                    priority_progress = PriorityProgress.empty()
                if next_message.transfer_priority:
                    active_transfer_priority = next_message.transfer_priority
                    active_incomplete_priority = None
                    active_incomplete_prompt_count = 0
                else:
                    active_transfer_priority = None
                    if next_message.incomplete_priority:
                        if active_incomplete_priority == next_message.incomplete_priority:
                            active_incomplete_prompt_count += 1
                        else:
                            active_incomplete_prompt_count = 1
                        active_incomplete_priority = next_message.incomplete_priority
                    else:
                        active_incomplete_priority = None
                        active_incomplete_prompt_count = 0
                user_response = await self._wait_for_user_response(context)

        except ConversationComplete as error:
            if str(error):
                await self._send_message(context.thread_id, str(error))
                return

    @step
    async def _load_rubric(self) -> dict[str, Any]:
        rubric_files = self._settings["rubric_path"]
        if isinstance(rubric_files, str):
            rubric_files = [rubric_files]

        loaded_rubric: dict[str, Any] = {}
        for rubric_file in rubric_files:
            file_contents = Path(rubric_file).read_text()
            if not file_contents.strip():
                continue

            parsed = yaml.safe_load(file_contents)
            if parsed:
                loaded_rubric |= parsed

        return loaded_rubric

    async def _wait_for_user_response(self, context: DuckContext) -> str:
        message = await wait_for_message(context.timeout)
        if message is None:
            raise ConversationComplete("This conversation has timed out.")
        return message["content"]

    async def _review_conversation(
            self,
            context: DuckContext,
            rubric: dict[str, Any],
            full_project: str,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            conversation_context: list[ConversationTurn],
            priority_progress: PriorityProgress,
    ) -> RubricAssessment:
        analysis_context = self._analysis_context(
            rubric,
            full_project,
            scenarios,
            current_scenario_index,
            conversation_context,
        )
        raw_response = await self._ai_client.run_agent(context, self._conversation_review_agent, analysis_context)
        return self._parse_assessment(
            raw_response,
            priority_progress,
            scenarios,
            current_scenario_index,
        )

    async def _review_incomplete_response(
            self,
            context: DuckContext,
            rubric: dict[str, Any],
            full_project: str,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            conversation_context: list[ConversationTurn],
            priority_item: PriorityItem | None = None,
            incomplete_prompt_count: int = 0,
    ) -> TAIncompleteDecision:
        process_context = self._incomplete_response_context(
            rubric,
            full_project,
            scenarios,
            current_scenario_index,
            conversation_context,
            priority_item,
            incomplete_prompt_count,
        )
        raw_response = await self._ai_client.run_agent(context, self._ta_incomplete_agent, process_context)
        return self._parse_ta_incomplete_response(raw_response)

    async def _review_unrelated_response(
            self,
            context: DuckContext,
            rubric: dict[str, Any],
            full_project: str,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            conversation_context: list[ConversationTurn],
    ) -> UnrelatedCompletion:
        process_context = self._process_context(
            rubric,
            full_project,
            scenarios,
            current_scenario_index,
            conversation_context,
        )
        raw_response = await self._ai_client.run_agent(context, self._unrelated_completion_agent, process_context)
        return self._parse_unrelated_completion(raw_response)

    async def _review_concept_transfer(
            self,
            context: DuckContext,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            priority_item: PriorityItem,
            conversation_context: list[ConversationTurn],
    ) -> ConceptTransferCompletion:
        process_context = self._concept_transfer_context(
            scenarios,
            current_scenario_index,
            priority_item,
            conversation_context,
        )
        raw_response = await self._ai_client.run_agent(context, self._concept_transfer_agent, process_context)
        return self._parse_concept_transfer(raw_response)

    def _first_message(self) -> str:
        return self._settings["first_message"]

    def _opening_message(
            self,
            rubric: dict[str, Any],
            full_project: str,
            scenarios: list[RubricScenario] | None = None,
    ) -> str:
        first_message = f"*{self._first_message().strip()}*"
        first_scenario = scenarios[0] if scenarios else None
        first_error = first_scenario.error if first_scenario else self._first_error(rubric)
        first_code = first_scenario.code if first_scenario and first_scenario.code.strip() else full_project
        message_parts = [
            first_message,
            "Here is the code and its associated error.\n\n\nCode:",
        ]
        if not first_code.strip():
            if first_error:
                message_parts.extend([
                    "This is what's happening when I run it.",
                    f"```\n{first_error}\n```",
                    self._priority_prompt("ask_error_meaning", self._error_type(first_error)),
                ])
            return "\n\n".join(message_parts)

        message_parts.append(f"```python\n{first_code.strip()}\n```")
        if first_error:
            message_parts.extend([
                "Error:",
                f"```\n{first_error}\n```",
                self._priority_prompt("ask_error_meaning", self._error_type(first_error)),
            ])
        return "\n\n".join(message_parts)

    async def _next_message(
            self,
            context: DuckContext,
            rubric: dict[str, Any],
            full_project: str,
            assessment: RubricAssessment,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            conversation_context: list[ConversationTurn],
    ) -> NextMessage:
        item_fulfilled = self._item_fulfilled(assessment)

        if assessment.rubric_finished and item_fulfilled:
            return NextMessage(
                random.choice(DEBUGGING_PRACTICE_RESPONSES["exercise_complete"]),
                True,
                current_scenario_index,
            )

        if item_fulfilled:
            next_scenario_index = current_scenario_index + 1
            if next_scenario_index >= len(scenarios):
                return NextMessage(
                    random.choice(DEBUGGING_PRACTICE_RESPONSES["exercise_complete"]),
                    True,
                    next_scenario_index,
                )

            next_error = scenarios[next_scenario_index].error
            next_code = scenarios[next_scenario_index].code or full_project
            message_parts = [
                random.choice(DEBUGGING_PRACTICE_RESPONSES["item_complete"]),
                random.choice(DEBUGGING_PRACTICE_RESPONSES["next_item"]),
            ]
            if next_code:
                message_parts.extend([
                    "Code for the next error:",
                    f"```python\n{next_code.strip()}\n```",
                ])
            if next_error:
                message_parts.extend([
                    "Traceback for the next error:",
                    f"```\n{next_error}\n```",
                    self._priority_prompt("ask_error_meaning", self._error_type(next_error)),
                ])
            return NextMessage("\n\n".join(message_parts), False, next_scenario_index)

        priority_item = self._priority_item_needing_attention(assessment)
        latest_priority = self._latest_attempted_priority_item(assessment)
        latest_priority_status = self._priority_status(assessment, latest_priority)

        if latest_priority and latest_priority_status == "incorrect":
            completion = await self._review_concept_transfer(
                context,
                scenarios,
                current_scenario_index,
                latest_priority,
                conversation_context,
            )
            if completion.concept_understood:
                assessment = self._assessment_with_understood_priority(
                    assessment,
                    latest_priority,
                )
                return await self._next_message(
                    context,
                    rubric,
                    full_project,
                    assessment,
                    scenarios,
                    current_scenario_index,
                    conversation_context,
                )

            if completion.response:
                return NextMessage(completion.response, False, current_scenario_index, latest_priority)

        if assessment.unrelated:
            completion = await self._review_unrelated_response(
                context,
                rubric,
                full_project,
                scenarios,
                current_scenario_index,
                conversation_context,
            )
            if completion.response:
                return NextMessage(completion.response, False, current_scenario_index)

        if latest_priority and latest_priority_status == "incomplete":
            decision = await self._review_incomplete_response(
                context,
                rubric,
                full_project,
                scenarios,
                current_scenario_index,
                conversation_context,
                latest_priority,
            )
            return NextMessage(
                self._incomplete_response_message(decision),
                False,
                current_scenario_index,
                incomplete_priority=latest_priority,
            )

        return NextMessage(
            self._priority_prompt_for_item(priority_item, scenarios, current_scenario_index),
            False,
            current_scenario_index,
        )

    async def _next_incomplete_subprocess_message(
            self,
            context: DuckContext,
            rubric: dict[str, Any],
            full_project: str,
            assessment: RubricAssessment,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            conversation_context: list[ConversationTurn],
            active_incomplete_priority: PriorityItem,
            active_incomplete_prompt_count: int,
    ) -> NextMessage:
        latest_priority = self._latest_attempted_priority_item(assessment)
        latest_priority_status = self._priority_status(assessment, latest_priority)

        if latest_priority_status == "incorrect":
            return await self._concept_transfer_next_message(
                context,
                rubric,
                full_project,
                assessment,
                scenarios,
                current_scenario_index,
                active_incomplete_priority,
                conversation_context,
            )

        if active_incomplete_prompt_count >= INCOMPLETE_PROMPTS_BEFORE_CONCEPT_TRANSFER:
            return await self._concept_transfer_next_message(
                context,
                rubric,
                full_project,
                assessment,
                scenarios,
                current_scenario_index,
                active_incomplete_priority,
                conversation_context,
            )

        decision = await self._review_incomplete_response(
            context,
            rubric,
            full_project,
            scenarios,
            current_scenario_index,
            conversation_context,
            active_incomplete_priority,
            active_incomplete_prompt_count,
        )
        return NextMessage(
            self._incomplete_response_message(decision),
            False,
            current_scenario_index,
            incomplete_priority=active_incomplete_priority,
        )

    async def _concept_transfer_next_message(
            self,
            context: DuckContext,
            rubric: dict[str, Any],
            full_project: str,
            assessment: RubricAssessment,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            priority_item: PriorityItem,
            conversation_context: list[ConversationTurn],
    ) -> NextMessage:
        completion = await self._review_concept_transfer(
            context,
            scenarios,
            current_scenario_index,
            priority_item,
            conversation_context,
        )
        if completion.concept_understood:
            assessment = self._assessment_with_understood_priority(
                assessment,
                priority_item,
            )
            return await self._next_message(
                context,
                rubric,
                full_project,
                assessment,
                scenarios,
                current_scenario_index,
                conversation_context,
            )
        return NextMessage(
            completion.response or self._priority_prompt_for_item(priority_item, scenarios, current_scenario_index),
            False,
            current_scenario_index,
            priority_item,
        )

    @staticmethod
    def _item_fulfilled(assessment: RubricAssessment) -> bool:
        return (
            assessment.rubric_item_fulfilled
            and all(
                DebuggingPracticeDuckWorkflow._priority_item_understood(assessment, priority_item)
                for priority_item in PRIORITY_ITEMS
            )
            and not assessment.unrelated
        )

    @staticmethod
    def _priority_item_understood(assessment: RubricAssessment, priority_item: PriorityItem) -> bool:
        priority = assessment.priorities.get(priority_item.key)
        return bool(priority and priority.fulfilled and priority.status == "fulfilled")

    @staticmethod
    def _priority_status(assessment: RubricAssessment, priority_item: PriorityItem | None) -> str:
        if priority_item is None:
            return "missing"

        priority = assessment.priorities.get(priority_item.key)
        if not priority:
            return "missing"
        return priority.status

    @staticmethod
    def _latest_student_response(conversation_context: list[ConversationTurn]) -> str:
        for speaker, message in reversed(conversation_context):
            if speaker == "TA":
                return message
        return ""

    @staticmethod
    def _latest_attempted_priority_item(assessment: RubricAssessment) -> PriorityItem | None:
        if assessment.latest_attempted_priority:
            return next(
                (
                    priority_item
                    for priority_item in PRIORITY_ITEMS
                    if priority_item.key == assessment.latest_attempted_priority
                ),
                None,
            )

        return next(
            (
                priority_item
                for priority_item in PRIORITY_ITEMS
                if (priority := assessment.priorities.get(priority_item.key)) and priority.latest_attempted
            ),
            None,
        )

    @staticmethod
    def _next_priority_item(assessment: RubricAssessment) -> PriorityItem:
        latest_attempted_priority = DebuggingPracticeDuckWorkflow._latest_attempted_priority_item(assessment)
        if latest_attempted_priority:
            priority_status = DebuggingPracticeDuckWorkflow._priority_status(
                assessment,
                latest_attempted_priority,
            )
            if priority_status in {"incorrect", "incomplete"}:
                return latest_attempted_priority

        for priority_item in PRIORITY_ITEMS:
            if not DebuggingPracticeDuckWorkflow._priority_item_understood(assessment, priority_item):
                return priority_item
        return PRIORITY_ITEMS[-1]

    @staticmethod
    def _priority_item_needing_attention(assessment: RubricAssessment) -> PriorityItem:
        return DebuggingPracticeDuckWorkflow._next_priority_item(assessment)

    @staticmethod
    def _priority_prompt_for_item(
            priority_item: PriorityItem,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
    ) -> str:
        current_scenario = (
            scenarios[current_scenario_index]
            if current_scenario_index < len(scenarios)
            else None
        )
        error_type = DebuggingPracticeDuckWorkflow._error_type(current_scenario.error if current_scenario else "")
        return DebuggingPracticeDuckWorkflow._priority_prompt(priority_item.prefab_bucket, error_type)

    @staticmethod
    def _priority_prompt(prefab_bucket: str, error_type: str = "error") -> str:
        prompt = random.choice(DEBUGGING_PRACTICE_RESPONSES[prefab_bucket])
        return prompt.format(error_type=error_type or "error")

    @staticmethod
    def _assessment_with_understood_priority(
            assessment: RubricAssessment,
            priority_item: PriorityItem,
    ) -> RubricAssessment:
        priorities = dict(assessment.priorities)
        priorities[priority_item.key] = PriorityAssessment(
            fulfilled=True,
            latest_attempted=False,
            status="fulfilled",
        )
        all_priorities_fulfilled = all(
            priority.fulfilled and priority.status == "fulfilled"
            for priority in priorities.values()
        )
        return replace(
            assessment,
            rubric_item_fulfilled=assessment.rubric_item_fulfilled or all_priorities_fulfilled,
            priorities=priorities,
            unrelated=False,
        )

    @staticmethod
    def _incomplete_response_message(decision: TAIncompleteDecision) -> str:
        if decision.student_response.strip():
            return decision.student_response.strip()

        if decision.incomplete_response_part.strip():
            return (
                f"I think this response is incomplete: {decision.incomplete_response_part.strip()}\n\n"
                "Would you explain that in more detail?"
            )

        return random.choice(DEBUGGING_PRACTICE_RESPONSES["retry_incomplete"])

    @staticmethod
    def _full_project(rubric: dict[str, Any]) -> str:
        full_project = rubric.get("full project", "")
        if isinstance(full_project, str):
            return full_project
        if full_project:
            return yaml.safe_dump(full_project)
        return ""

    @staticmethod
    def _first_error(rubric: dict[str, Any]) -> str:
        for value in rubric.values():
            error = DebuggingPracticeDuckWorkflow._first_traceback(value)
            if error:
                return error
        return ""

    @staticmethod
    def _first_traceback(value: Any) -> str:
        if isinstance(value, str):
            return DebuggingPracticeDuckWorkflow._traceback_from_string(value)

        if isinstance(value, dict):
            if "traceback" in value:
                return DebuggingPracticeDuckWorkflow._traceback_text(value["traceback"])

            for nested_value in value.values():
                error = DebuggingPracticeDuckWorkflow._first_traceback(nested_value)
                if error:
                    return error
            return ""

        if isinstance(value, list):
            for nested_value in value:
                error = DebuggingPracticeDuckWorkflow._first_traceback(nested_value)
                if error:
                    return error
        return ""

    @staticmethod
    def _traceback_text(value: Any) -> str:
        if isinstance(value, str):
            return DebuggingPracticeDuckWorkflow._traceback_from_string(value) or value.strip()

        if isinstance(value, list):
            for nested_value in value:
                error = DebuggingPracticeDuckWorkflow._traceback_text(nested_value)
                if error:
                    return error
            return ""

        if isinstance(value, dict):
            for nested_value in value.values():
                error = DebuggingPracticeDuckWorkflow._traceback_text(nested_value)
                if error:
                    return error
        return ""

    @staticmethod
    def _traceback_from_string(value: str) -> str:
        lines = value.splitlines()
        for index, line in enumerate(lines):
            if line.strip() != "Traceback (most recent call last):":
                continue

            traceback_lines = []
            for traceback_line in lines[index:]:
                if traceback_lines and not traceback_line.strip():
                    break
                traceback_lines.append(traceback_line.rstrip())
            return "\n".join(traceback_lines).strip()

        return ""

    @staticmethod
    def _error_type(error: str) -> str:
        for line in reversed(error.splitlines()):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            if ":" in stripped_line:
                candidate = stripped_line.split(":", 1)[0].strip()
            else:
                candidate = stripped_line.split(maxsplit=1)[0].strip()
            if candidate.endswith("Error") or candidate in {"Exception", "SyntaxError"}:
                return candidate
        return "error"

    @staticmethod
    def _rubric_field_text(value: Any, field_name: str) -> str:
        if not isinstance(value, dict) or field_name not in value:
            return ""

        return DebuggingPracticeDuckWorkflow._field_text(value[field_name])

    @staticmethod
    def _field_text(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()

        if isinstance(value, list):
            return "\n".join(
                field_text
                for item in value
                if (field_text := DebuggingPracticeDuckWorkflow._field_text(item))
            ).strip()

        if isinstance(value, dict):
            return yaml.safe_dump(value, sort_keys=False).strip()

        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _rubric_scenarios(rubric: dict[str, Any]) -> list[RubricScenario]:
        scenarios: list[RubricScenario] = []

        def walk(value: Any, path: list[str]) -> None:
            if isinstance(value, dict):
                if "traceback" in value:
                    name = " > ".join(path) if path else "rubric item"
                    scenarios.append(RubricScenario(
                        name=name,
                        rubric_item=yaml.safe_dump(value, sort_keys=False).strip(),
                        error=DebuggingPracticeDuckWorkflow._first_traceback(value),
                        code=DebuggingPracticeDuckWorkflow._rubric_field_text(value, "code"),
                        error_line=DebuggingPracticeDuckWorkflow._rubric_field_text(value, "error line"),
                        intended_behavior=DebuggingPracticeDuckWorkflow._rubric_field_text(value, "intended behavior"),
                        required_fix=DebuggingPracticeDuckWorkflow._rubric_field_text(value, "required fix"),
                        required_concept=DebuggingPracticeDuckWorkflow._rubric_field_text(value, "required concept"),
                    ))
                    return

                for key, nested_value in value.items():
                    if key == "full project":
                        continue
                    walk(nested_value, [*path, str(key)])
                return

            if isinstance(value, list):
                for index, nested_value in enumerate(value, start=1):
                    if isinstance(nested_value, str):
                        name = " > ".join(path) if path else f"rubric item {index}"
                        scenarios.append(RubricScenario(
                            name=name,
                            rubric_item=nested_value,
                            error=DebuggingPracticeDuckWorkflow._first_traceback(nested_value),
                            code="",
                            error_line="",
                            intended_behavior="",
                            required_fix="",
                            required_concept="",
                        ))
                    else:
                        walk(nested_value, [*path, str(index)])

        walk(rubric, [])
        return scenarios

    @staticmethod
    def _parse_assessment(
            raw_response: str | None,
            priority_progress: PriorityProgress | None = None,
            scenarios: list[RubricScenario] | None = None,
            current_scenario_index: int = 0,
    ) -> RubricAssessment:
        if priority_progress is None:
            priority_progress = PriorityProgress.empty()
        if scenarios is None:
            scenarios = []

        if not raw_response:
            return DebuggingPracticeDuckWorkflow._assessment_from_progress(
                priority_progress,
                PriorityObservation([], None, "missing"),
                scenarios,
                current_scenario_index,
            )

        raw_response = DebuggingPracticeDuckWorkflow._unwrap_json_markdown(raw_response)

        try:
            payload = RubricAssessmentResponse.model_validate_json(raw_response)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return DebuggingPracticeDuckWorkflow._assessment_from_progress(
                priority_progress,
                PriorityObservation([], None, "missing"),
                scenarios,
                current_scenario_index,
            )

        latest_attempted_priority = DebuggingPracticeDuckWorkflow._normalize_priority_key(
            payload.latest_attempted_priority
        )
        latest_attempted_status = DebuggingPracticeDuckWorkflow._normalize_priority_status(
            payload.latest_attempted_status,
        )
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
        observation = DebuggingPracticeDuckWorkflow._observation_with_fix_implications(
            observation,
            scenarios,
            current_scenario_index,
        )
        return DebuggingPracticeDuckWorkflow._assessment_from_progress(
            priority_progress.apply(observation),
            observation,
            scenarios,
            current_scenario_index,
        )

    @staticmethod
    def _observation_with_fix_implications(
            observation: PriorityObservation,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
    ) -> PriorityObservation:
        if (
                observation.unrelated
                or observation.latest_attempted_priority != "fix"
                or observation.latest_attempted_status != "fulfilled"
        ):
            return observation

        current_scenario = (
            scenarios[current_scenario_index]
            if current_scenario_index < len(scenarios)
            else None
        )
        if not current_scenario or not current_scenario.required_fix.strip():
            return observation

        fulfilled_priorities = list(dict.fromkeys([
            *observation.fulfilled_priorities,
            "fix",
            "error_location",
            "intended_behavior",
        ]))
        return replace(observation, fulfilled_priorities=fulfilled_priorities)

    @staticmethod
    def _assessment_from_progress(
            priority_progress: PriorityProgress,
            observation: PriorityObservation,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
    ) -> RubricAssessment:
        item_fulfilled = all(
            DebuggingPracticeDuckWorkflow._priority_item_understood_from_progress(
                priority_progress,
                priority_item,
            )
            for priority_item in PRIORITY_ITEMS
        )
        rubric_finished = item_fulfilled and current_scenario_index + 1 >= len(scenarios)
        next_rubric_item = None
        if item_fulfilled and not rubric_finished and current_scenario_index + 1 < len(scenarios):
            next_rubric_item = scenarios[current_scenario_index + 1].name

        return RubricAssessment(
            rubric_finished=rubric_finished,
            rubric_item_fulfilled=item_fulfilled,
            next_rubric_item=next_rubric_item,
            latest_attempted_priority=observation.latest_attempted_priority,
            priorities=priority_progress.priorities,
            unrelated=observation.unrelated,
            reason_for_evaluations=observation.reason_for_evaluations,
        )

    @staticmethod
    def _priority_item_understood_from_progress(
            priority_progress: PriorityProgress,
            priority_item: PriorityItem,
    ) -> bool:
        priority = priority_progress.priorities.get(priority_item.key)
        return bool(priority and priority.fulfilled and priority.status == "fulfilled")

    @staticmethod
    def _empty_assessment() -> RubricAssessment:
        return RubricAssessment(
            rubric_finished=False,
            rubric_item_fulfilled=False,
            next_rubric_item=None,
            latest_attempted_priority=None,
            priorities=PriorityProgress.empty().priorities,
        )

    @staticmethod
    def _default_priorities() -> dict[str, PriorityAssessment]:
        return PriorityProgress.empty().priorities

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
    def _parse_ta_incomplete_response(raw_response: str | None) -> TAIncompleteDecision:
        if not raw_response:
            return TAIncompleteDecision(
                reasoning="",
                incomplete_response_part="",
                student_response="",
            )

        raw_response = DebuggingPracticeDuckWorkflow._unwrap_json_markdown(raw_response)
        try:
            payload = TAIncompleteResponse.model_validate_json(raw_response)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return TAIncompleteDecision(
                reasoning="",
                incomplete_response_part="",
                student_response="",
            )

        return TAIncompleteDecision(
            reasoning=payload.reasoning,
            incomplete_response_part=payload.incomplete_response_part,
            student_response=payload.student_response,
        )

    @staticmethod
    def _parse_unrelated_completion(raw_response: str | None) -> UnrelatedCompletion:
        if not raw_response:
            return UnrelatedCompletion(reasoning="", response=random.choice(DEBUGGING_PRACTICE_RESPONSES["retry_fix"]))

        raw_response = DebuggingPracticeDuckWorkflow._unwrap_json_markdown(raw_response)
        try:
            payload = UnrelatedCompletionResponse.model_validate_json(raw_response)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return UnrelatedCompletion(reasoning="", response=random.choice(DEBUGGING_PRACTICE_RESPONSES["retry_fix"]))

        return UnrelatedCompletion(reasoning=payload.reasoning, response=payload.response)

    @staticmethod
    def _parse_concept_transfer(raw_response: str | None) -> ConceptTransferCompletion:
        if not raw_response:
            return ConceptTransferCompletion(
                reasoning="",
                concept_understood=False,
                response=random.choice(DEBUGGING_PRACTICE_RESPONSES["retry_fix"]),
            )

        raw_response = DebuggingPracticeDuckWorkflow._unwrap_json_markdown(raw_response)
        try:
            payload = ConceptTransferResponse.model_validate_json(raw_response)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return ConceptTransferCompletion(
                reasoning="",
                concept_understood=False,
                response=random.choice(DEBUGGING_PRACTICE_RESPONSES["retry_fix"]),
            )

        return ConceptTransferCompletion(
            reasoning=payload.reasoning,
            concept_understood=payload.concept_understood,
            response=payload.response,
        )

    @staticmethod
    def _unwrap_json_markdown(raw_response: str) -> str:
        raw_response = raw_response.strip()
        if raw_response.startswith("```"):
            raw_response = raw_response.strip("`").strip()
            if raw_response.startswith("json"):
                raw_response = raw_response[4:].strip()
        return raw_response

    @staticmethod
    def _analysis_context(
            rubric: dict[str, Any],
            full_project: str,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            conversation_context: list[ConversationTurn],
    ) -> str:
        rubric_text = yaml.safe_dump(rubric, sort_keys=False).strip()
        current_scenario = (
            scenarios[current_scenario_index]
            if current_scenario_index < len(scenarios)
            else None
        )
        remaining_scenarios = scenarios[current_scenario_index + 1:]
        current_scenario_text = yaml.safe_dump(
            {
                "name": current_scenario.name,
                "rubric_item": current_scenario.rubric_item,
                "traceback": current_scenario.error,
                "code": current_scenario.code,
                "error line": current_scenario.error_line,
                "intended behavior": current_scenario.intended_behavior,
                "required fix": current_scenario.required_fix,
                "required concept": current_scenario.required_concept,
            } if current_scenario else {},
            sort_keys=False,
        ).strip()
        remaining_scenario_names = [
            scenario.name
            for scenario in remaining_scenarios
        ]
        conversation = "\n\n".join(
            f"{speaker}: {message.strip()}"
            for speaker, message in conversation_context
        )
        return "\n\n".join([
            "Assess the TA responses in the conversation against the current rubric item.",
            "Return only a JSON object with these keys:",
            (
                "reason for evaluations, latest_attempted_priority, latest_attempted_status, "
                "fulfilled_priorities, unrelated"
            ),
            "Rubric and traceback scenarios:",
            rubric_text,
            "Current rubric item:",
            current_scenario_text,
            "Remaining rubric item names:",
            yaml.safe_dump(remaining_scenario_names, sort_keys=False).strip(),
            "Current full project:",
            f"```python\n{full_project.strip()}\n```",
            "Conversation:",
            conversation,
        ])

    @staticmethod
    def _process_context(
            rubric: dict[str, Any],
            full_project: str,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            conversation_context: list[ConversationTurn],
    ) -> str:
        rubric_text = yaml.safe_dump(rubric, sort_keys=False).strip()
        current_scenario = (
            scenarios[current_scenario_index]
            if current_scenario_index < len(scenarios)
            else None
        )
        current_scenario_text = yaml.safe_dump(
            {
                "name": current_scenario.name,
                "rubric_item": current_scenario.rubric_item,
                "traceback": current_scenario.error,
                "code": current_scenario.code,
                "error line": current_scenario.error_line,
                "intended behavior": current_scenario.intended_behavior,
                "required fix": current_scenario.required_fix,
                "required concept": current_scenario.required_concept,
            } if current_scenario else {},
            sort_keys=False,
        ).strip()
        conversation = "\n\n".join(
            f"{speaker}: {message.strip()}"
            for speaker, message in conversation_context
        )
        context_parts = [
            "Rubric and traceback scenarios:",
            rubric_text,
            "Current rubric item:",
            current_scenario_text,
            "Current full project:",
            f"```python\n{full_project.strip()}\n```",
            "Conversation:",
            conversation,
        ]
        return "\n\n".join(context_parts)

    @staticmethod
    def _incomplete_response_context(
            rubric: dict[str, Any],
            full_project: str,
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            conversation_context: list[ConversationTurn],
            priority_item: PriorityItem | None = None,
            incomplete_prompt_count: int = 0,
    ) -> str:
        base_context = DebuggingPracticeDuckWorkflow._process_context(
            rubric,
            full_project,
            scenarios,
            current_scenario_index,
            conversation_context,
        )
        subprocess_context = {
            "active incomplete-response subprocess": priority_item is not None,
            "target priority topic": priority_item.label if priority_item else "",
            "target priority key": priority_item.key if priority_item else "",
            "incomplete-response prompts already sent": incomplete_prompt_count,
        }
        return "\n\n".join([
            "Create a temporary incomplete-response support message for a debugging-practice conversation.",
            base_context,
            "Incomplete-response subprocess context:",
            yaml.safe_dump(subprocess_context, sort_keys=False).strip(),
        ])

    @staticmethod
    def _concept_transfer_context(
            scenarios: list[RubricScenario],
            current_scenario_index: int,
            priority_item: PriorityItem,
            conversation_context: list[ConversationTurn],
    ) -> str:
        current_scenario = (
            scenarios[current_scenario_index]
            if current_scenario_index < len(scenarios)
            else None
        )
        concept_focus = (
            "how to trace an error"
            if priority_item.key == "error_location"
            else "the concept the error tests"
        )
        context = {
            "failed priority topic": priority_item.label,
            "current rubric item": {
                "name": current_scenario.name,
                "rubric_item": current_scenario.rubric_item,
                "traceback": current_scenario.error,
                "code": current_scenario.code,
                "error line": current_scenario.error_line,
                "intended behavior": current_scenario.intended_behavior,
                "required fix": current_scenario.required_fix,
            } if current_scenario else {},
            "concept support focus": concept_focus,
            "required concept": current_scenario.required_concept if current_scenario else "",
            "conversation context": "\n\n".join(
                f"{speaker}: {message.strip()}"
                for speaker, message in conversation_context
            ),
        }
        return "\n\n".join([
            "Create a temporary concept-support response for a debugging-practice conversation.",
            yaml.safe_dump(context, sort_keys=False).strip(),
        ])
