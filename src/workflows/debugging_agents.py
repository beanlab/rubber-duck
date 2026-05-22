import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DuckContext
from .debugging_rubric import Rubric
from .debugging_schema import (
    ConceptTransferCompletion,
    RubricAssessment,
    TAIncompleteDecision,
    UnrelatedCompletion,
    ValidationSchema,
)

ConversationTurn = tuple[str, str]

PROMPT_DIRECTORY = Path(__file__).parents[1] / "prompts" / "debugging-practice-duck"
TA_INCOMPLETE_PROMPT_PATH = PROMPT_DIRECTORY / "TA-incomplete.md"
UNRELATED_COMPLETIONS_PROMPT_PATH = PROMPT_DIRECTORY / "unrelated-completions.md"
CONCEPT_TRANSFER_PROMPT_PATH = PROMPT_DIRECTORY / "concept-transfer.md"

PRIORITY_BUCKETS = {
    "error_meaning": "ask_error_meaning",
    "error_location": "ask_error_location",
    "intended_behavior": "ask_intended_behavior",
    "fix": "ask_for_fix",
}
PRIORITY_ORDER = list(PRIORITY_BUCKETS)
INCOMPLETE_PROMPTS_BEFORE_CONCEPT_TRANSFER = 1


@dataclass(frozen=True)
class NextMessage:
    response: str
    is_finished: bool
    scenario_index: int
    transfer_priority: str | None = None
    incomplete_priority: str | None = None


def _load_debugging_practice_responses() -> dict[str, list[str]]:
    responses_path = PROMPT_DIRECTORY / "prefabs.yaml"
    with responses_path.open(encoding="utf-8") as prefab_file:
        responses = yaml.safe_load(prefab_file) or {}
    return {
        key: value
        for key, value in responses.items()
        if isinstance(value, list)
    }


DEBUGGING_PRACTICE_RESPONSES = _load_debugging_practice_responses()


class DuckAgent:
    def __init__(
            self,
            conversation_review_agent: Agent,
            ai_client: AIClient,
            incomplete_subprocess: Agent | None = None,
            incorrect_subprocess: Agent | None = None,
    ):
        self._conversation_review_agent = conversation_review_agent
        self._ai_client = ai_client
        self._validation = ValidationSchema()
        self._configure_rubric_assessment_agent(self._conversation_review_agent)
        self._ta_incomplete_agent = self._process_agent(
            incomplete_subprocess,
            "incomplete_subprocess",
            TA_INCOMPLETE_PROMPT_PATH,
            ValidationSchema.ta_incomplete_output_format,
        )
        self._unrelated_completion_agent = self._process_agent(
            None,
            "debugging_practice_unrelated_completion",
            UNRELATED_COMPLETIONS_PROMPT_PATH,
            ValidationSchema.unrelated_completion_output_format,
        )
        self._concept_transfer_agent = self._process_agent(
            incorrect_subprocess,
            "incorrect_subprocess",
            CONCEPT_TRANSFER_PROMPT_PATH,
            ValidationSchema.concept_transfer_output_format,
        )

    def _configure_rubric_assessment_agent(self, agent: Agent) -> None:
        agent.prompt = (PROMPT_DIRECTORY / "eval-step.md").read_text(encoding="utf-8")
        agent.output_format = ValidationSchema.rubric_assessment_output_format

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

    async def review_conversation(
            self,
            context: DuckContext,
            rubric: Rubric,
            conversation_context: list[ConversationTurn],
    ) -> RubricAssessment:
        analysis_context = self._analysis_context(
            rubric,
            conversation_context,
        )
        return await self._run_validated_agent(
            context,
            self._conversation_review_agent,
            analysis_context,
            self._validation.parse_assessment,
            rubric.priorities,
            rubric.next_scenario_name,
            rubric.current_scenario.required_fix if rubric.current_scenario else "",
        )

    async def review_incomplete_response(
            self,
            context: DuckContext,
            rubric: Rubric,
            conversation_context: list[ConversationTurn],
            priority_key: str | None = None,
            incomplete_prompt_count: int = 0,
    ) -> TAIncompleteDecision:
        process_context = self._incomplete_response_context(
            rubric,
            conversation_context,
            priority_key,
            incomplete_prompt_count,
        )
        return await self._run_validated_agent(
            context,
            self._ta_incomplete_agent,
            process_context,
            self._validation.parse_ta_incomplete_response,
        )

    async def review_unrelated_response(
            self,
            context: DuckContext,
            rubric: Rubric,
            conversation_context: list[ConversationTurn],
    ) -> UnrelatedCompletion:
        process_context = self._process_context(
            rubric,
            conversation_context,
        )
        return await self._run_validated_agent(
            context,
            self._unrelated_completion_agent,
            process_context,
            self._validation.parse_unrelated_completion,
        )

    async def review_concept_transfer(
            self,
            context: DuckContext,
            rubric: Rubric,
            conversation_context: list[ConversationTurn],
            priority_key: str,
    ) -> ConceptTransferCompletion:
        process_context = self._concept_transfer_context(
            rubric,
            priority_key,
            conversation_context,
        )
        return await self._run_validated_agent(
            context,
            self._concept_transfer_agent,
            process_context,
            self._validation.parse_concept_transfer,
        )

    async def next_message(
            self,
            context: DuckContext,
            rubric: Rubric,
            assessment: RubricAssessment,
            conversation_context: list[ConversationTurn],
    ) -> NextMessage:
        item_fulfilled = self._item_fulfilled(assessment)

        if assessment.rubric_finished and item_fulfilled:
            return NextMessage(
                random.choice(DEBUGGING_PRACTICE_RESPONSES["exercise_complete"]),
                True,
                rubric.current_scenario_index,
            )

        if item_fulfilled:
            next_scenario_index = rubric.current_scenario_index + 1
            if next_scenario_index >= len(rubric.scenarios):
                return NextMessage(
                    random.choice(DEBUGGING_PRACTICE_RESPONSES["exercise_complete"]),
                    True,
                    next_scenario_index,
                )

            next_scenario = rubric.scenarios[next_scenario_index]
            message_parts = [
                random.choice(DEBUGGING_PRACTICE_RESPONSES["item_complete"]),
                random.choice(DEBUGGING_PRACTICE_RESPONSES["next_item"]),
            ]
            if next_scenario.code:
                message_parts.extend([
                    "Code for the next error:",
                    f"```python\n{next_scenario.code.strip()}\n```",
                ])
            if next_scenario.error:
                message_parts.extend([
                    "Traceback for the next error:",
                    f"```\n{next_scenario.error}\n```",
                    self._priority_prompt("ask_error_meaning", self._error_type(next_scenario.error)),
                ])
            return NextMessage("\n\n".join(message_parts), False, next_scenario_index)

        priority_key = self._priority_item_needing_attention(assessment)
        latest_priority = self._latest_attempted_priority_key(assessment)
        latest_priority_status = self._priority_status(assessment, latest_priority)

        if latest_priority and latest_priority_status == "incorrect":
            completion = await self.review_concept_transfer(
                context,
                rubric,
                conversation_context,
                latest_priority,
            )
            if completion.concept_understood:
                rubric.mark_priority_fulfilled(latest_priority)
                assessment = self.apply_understood_priority(
                    assessment,
                    latest_priority,
                )
                return await self.next_message(
                    context,
                    rubric,
                    assessment,
                    conversation_context,
                )

            if completion.response:
                return NextMessage(completion.response, False, rubric.current_scenario_index, latest_priority)

            return NextMessage(
                self._priority_prompt_for_item(latest_priority, rubric),
                False,
                rubric.current_scenario_index,
                latest_priority,
            )

        if assessment.unrelated:
            completion = await self.review_unrelated_response(
                context,
                rubric,
                conversation_context,
            )
            if completion.response:
                return NextMessage(completion.response, False, rubric.current_scenario_index)

            return NextMessage(
                random.choice(DEBUGGING_PRACTICE_RESPONSES["retry_fix"]),
                False,
                rubric.current_scenario_index,
            )

        if latest_priority and latest_priority_status == "incomplete":
            decision = await self.review_incomplete_response(
                context,
                rubric,
                conversation_context,
                latest_priority,
            )
            return NextMessage(
                self._incomplete_response_message(decision),
                False,
                rubric.current_scenario_index,
                incomplete_priority=latest_priority,
            )

        return NextMessage(
            self._priority_prompt_for_item(priority_key, rubric),
            False,
            rubric.current_scenario_index,
        )

    async def next_incomplete_subprocess_message(
            self,
            context: DuckContext,
            rubric: Rubric,
            assessment: RubricAssessment,
            conversation_context: list[ConversationTurn],
            active_incomplete_priority: str,
            active_incomplete_prompt_count: int,
    ) -> NextMessage:
        latest_priority = self._latest_attempted_priority_key(assessment)
        latest_priority_status = self._priority_status(assessment, latest_priority)

        if latest_priority_status == "incorrect":
            return await self.concept_transfer_next_message(
                context,
                rubric,
                assessment,
                conversation_context,
                active_incomplete_priority,
            )

        if active_incomplete_prompt_count >= INCOMPLETE_PROMPTS_BEFORE_CONCEPT_TRANSFER:
            return await self.concept_transfer_next_message(
                context,
                rubric,
                assessment,
                conversation_context,
                active_incomplete_priority,
            )

        decision = await self.review_incomplete_response(
            context,
            rubric,
            conversation_context,
            active_incomplete_priority,
            active_incomplete_prompt_count,
        )
        return NextMessage(
            self._incomplete_response_message(decision),
            False,
            rubric.current_scenario_index,
            incomplete_priority=active_incomplete_priority,
        )

    async def concept_transfer_next_message(
            self,
            context: DuckContext,
            rubric: Rubric,
            assessment: RubricAssessment,
            conversation_context: list[ConversationTurn],
            priority_key: str,
    ) -> NextMessage:
        completion = await self.review_concept_transfer(
            context,
            rubric,
            conversation_context,
            priority_key,
        )
        if completion.concept_understood:
            rubric.mark_priority_fulfilled(priority_key)
            assessment = self.apply_understood_priority(
                assessment,
                priority_key,
            )
            return await self.next_message(
                context,
                rubric,
                assessment,
                conversation_context,
            )
        return NextMessage(
            completion.response or self._priority_prompt_for_item(priority_key, rubric),
            False,
            rubric.current_scenario_index,
            priority_key,
        )

    @staticmethod
    def priority_item_understood(assessment: RubricAssessment, priority_key: str) -> bool:
        priority = assessment.priorities.get(priority_key)
        return bool(priority and priority.fulfilled and priority.status == "fulfilled")

    @staticmethod
    def apply_understood_priority(assessment: RubricAssessment, priority_key: str) -> RubricAssessment:
        priorities = dict(assessment.priorities)
        current = priorities.get(priority_key)
        if current:
            priorities[priority_key] = type(current)(
                fulfilled=True,
                latest_attempted=False,
                status="fulfilled",
            )
        all_priorities_fulfilled = all(
            priority.fulfilled and priority.status == "fulfilled"
            for priority in priorities.values()
        )
        return type(assessment)(
            rubric_finished=assessment.rubric_finished or all_priorities_fulfilled,
            rubric_item_fulfilled=assessment.rubric_item_fulfilled or all_priorities_fulfilled,
            next_rubric_item=assessment.next_rubric_item,
            latest_attempted_priority=assessment.latest_attempted_priority,
            priorities=priorities,
            unrelated=False,
            reason_for_evaluations=assessment.reason_for_evaluations,
        )

    def _item_fulfilled(self, assessment: RubricAssessment) -> bool:
        return (
            assessment.rubric_item_fulfilled
            and all(
                self.priority_item_understood(assessment, priority_key)
                for priority_key in PRIORITY_ORDER
            )
            and not assessment.unrelated
        )

    @staticmethod
    def _priority_status(assessment: RubricAssessment, priority_key: str | None) -> str:
        if priority_key is None:
            return "missing"

        priority = assessment.priorities.get(priority_key)
        if not priority:
            return "missing"
        return priority.status

    @staticmethod
    def _latest_attempted_priority_key(assessment: RubricAssessment) -> str | None:
        if assessment.latest_attempted_priority:
            return assessment.latest_attempted_priority

        return next(
            (
                priority_key
                for priority_key, priority in assessment.priorities.items()
                if priority.latest_attempted
            ),
            None,
        )

    @staticmethod
    def _next_priority_key(assessment: RubricAssessment) -> str:
        latest_attempted_priority = DuckAgent._latest_attempted_priority_key(assessment)
        if latest_attempted_priority:
            priority_status = DuckAgent._priority_status(
                assessment,
                latest_attempted_priority,
            )
            if priority_status in {"incorrect", "incomplete"}:
                return latest_attempted_priority

        for priority_key in PRIORITY_ORDER:
            if not DuckAgent.priority_item_understood(assessment, priority_key):
                return priority_key
        return PRIORITY_ORDER[-1]

    @staticmethod
    def _priority_item_needing_attention(assessment: RubricAssessment) -> str:
        return DuckAgent._next_priority_key(assessment)

    @staticmethod
    def _priority_prompt_for_item(priority_key: str, rubric: Rubric) -> str:
        current_error = rubric.current_scenario.error if rubric.current_scenario else ""
        error_type = DuckAgent._error_type(current_error)
        return DuckAgent._priority_prompt(PRIORITY_BUCKETS[priority_key], error_type)

    @staticmethod
    def _priority_prompt(prefab_bucket: str, error_type: str = "error") -> str:
        prompt = random.choice(DEBUGGING_PRACTICE_RESPONSES[prefab_bucket])
        return prompt.format(error_type=error_type or "error")

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
    def _analysis_context(
            rubric: Rubric,
            conversation_context: list[ConversationTurn],
    ) -> str:
        rubric_text = yaml.safe_dump(
            {
                "full project": rubric.full_project,
                "current scenario": rubric.current_scenario.name if rubric.current_scenario else "",
                "current scenario index": rubric.current_scenario_index,
                "remaining scenarios": [scenario.name for scenario in rubric.scenarios[rubric.current_scenario_index + 1 :]],
                "priorities": rubric.priorities,
            },
            sort_keys=False,
        ).strip()
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
            DuckAgent._current_scenario_text(rubric),
            "Remaining rubric item names:",
            yaml.safe_dump(
                DuckAgent._remaining_scenario_names(rubric),
                sort_keys=False,
            ).strip(),
            "Current full project:",
            f"```python\n{rubric.full_project.strip()}\n```",
            "Conversation:",
            DuckAgent._conversation_text(conversation_context),
        ])

    @staticmethod
    def _process_context(
            rubric: Rubric,
            conversation_context: list[ConversationTurn],
    ) -> str:
        return "\n\n".join([
            "Use the current rubric item and the conversation history to decide the next response.",
            "Current rubric item:",
            DuckAgent._current_scenario_text(rubric),
            "Conversation:",
            DuckAgent._conversation_text(conversation_context),
        ])

    @staticmethod
    def _incomplete_response_context(
            rubric: Rubric,
            conversation_context: list[ConversationTurn],
            priority_key: str | None,
            incomplete_prompt_count: int,
    ) -> str:
        return "\n\n".join([
            "Decide how to respond to the student's incomplete debugging explanation.",
            f"Incomplete prompt count: {incomplete_prompt_count}",
            f"Active priority: {priority_key or 'none'}",
            "Current rubric item:",
            DuckAgent._current_scenario_text(rubric),
            "Conversation:",
            DuckAgent._conversation_text(conversation_context),
        ])

    @staticmethod
    def _concept_transfer_context(
            rubric: Rubric,
            priority_key: str,
            conversation_context: list[ConversationTurn],
    ) -> str:
        return "\n\n".join([
            "Decide whether the student understands the debugging concept well enough to move on.",
            f"Priority topic: {priority_key}",
            "Current rubric item:",
            DuckAgent._current_scenario_text(rubric),
            "Conversation:",
            DuckAgent._conversation_text(conversation_context),
        ])

    @staticmethod
    def _current_scenario_text(rubric: Rubric) -> str:
        current_scenario = rubric.current_scenario
        return yaml.safe_dump(
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

    @staticmethod
    def _conversation_text(conversation_context: list[ConversationTurn]) -> str:
        return "\n\n".join(
            f"{speaker}: {message.strip()}"
            for speaker, message in conversation_context
        )

    @staticmethod
    def _remaining_scenario_names(rubric: Rubric) -> list[str]:
        return [
            scenario.name
            for scenario in rubric.scenarios[rubric.current_scenario_index + 1:]
        ]

    async def _run_validated_agent(
            self,
            context: DuckContext,
            agent: Agent,
            prompt_context: str,
            parser,
            *parser_args,
    ):
        raw_response = await self._ai_client.run_agent(context, agent, prompt_context)
        return parser(raw_response, *parser_args)

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
