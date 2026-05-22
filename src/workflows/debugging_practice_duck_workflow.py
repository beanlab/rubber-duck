import random
from pathlib import Path
from typing import Any

import yaml

from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import DebuggingPracticeDuckSettings, DuckContext
from ..utils.message_utils import wait_for_message
from ..utils.protocols import ConversationComplete
from .debugging_agents import DuckAgent, NextMessage, PRIORITY_BUCKETS
from .debugging_rubric import Rubric


ConversationTurn = tuple[str, str]
DEBUGGING_PRACTICE_FEEDBACK_MESSAGE = (
    "*The debugging practice duck is an experimental feature that is actively being developed. "
    "Please leave feedback as to your experience using the duck.*"
)


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
        self._send_message = send_message
        self._settings = settings
        self._duck_agent = DuckAgent(
            conversation_review_agent,
            ai_client,
            incomplete_subprocess,
            incorrect_subprocess,
        )

    async def __call__(self, context: DuckContext):
        try:
            conversation_context: list[ConversationTurn] = []
            rubric = Rubric.from_rubric_data(await self._load_rubric())

            opening_message = self._opening_message(rubric)
            conversation_context.append(("Student", opening_message))
            await self._send_message(context.thread_id, opening_message)
            user_response = await self._wait_for_user_response(context)

            for _ in _review_turns(self._settings):
                conversation_context.append(("TA", user_response))

                assessment = await self._duck_agent.review_conversation(
                    context,
                    rubric,
                    conversation_context,
                )
                rubric.apply_fulfilled_priorities(
                    priority_key
                    for priority_key, priority_state in assessment.priorities.items()
                    if priority_state.fulfilled
                )

                next_message = await self._resolve_next_message(
                    context,
                    rubric,
                    assessment,
                    conversation_context,
                )

                if not next_message.response:
                    return

                conversation_context.append(("Student", next_message.response))
                await self._send_message(context.thread_id, next_message.response)
                if next_message.is_finished:
                    rubric.advance_scenario()
                    await self._send_message(context.thread_id, DEBUGGING_PRACTICE_FEEDBACK_MESSAGE)
                    return

                self._apply_next_message_state(rubric, next_message)

                user_response = await self._wait_for_user_response(context)

        except ConversationComplete as error:
            if str(error):
                await self._send_message(context.thread_id, str(error))
                return

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

    def _opening_message(self, rubric: Rubric) -> str:
        message_parts = [
            f"*{self._settings['first_message'].strip()}*",
            "Here is the code and its associated error.\n\n\nCode:",
        ]
        first_scenario = rubric.current_scenario
        first_code = first_scenario.code if first_scenario and first_scenario.code.strip() else rubric.full_project
        first_error = first_scenario.error if first_scenario else rubric.first_error

        if first_code.strip():
            message_parts.append(f"```python\n{first_code.strip()}\n```")
            if first_error:
                message_parts.extend([
                    "Error:",
                    f"```\n{first_error}\n```",
                    self._priority_prompt("ask_error_meaning", self._error_type(first_error)),
                ])
            return "\n\n".join(message_parts)

        if first_error:
            message_parts.extend([
                "This is what's happening when it is run.",
                f"```\n{first_error}\n```",
                self._priority_prompt("ask_error_meaning", self._error_type(first_error)),
            ])
        return "\n\n".join(message_parts)

    @staticmethod
    def _apply_next_message_state(rubric: Rubric, next_message: NextMessage) -> None:
        if next_message.scenario_index != rubric.current_scenario_index:
            rubric.advance_scenario()

        if next_message.transfer_priority:
            rubric.set_active_transfer_priority(next_message.transfer_priority)
            rubric.set_active_incomplete_priority(None)
            rubric.reset_incomplete_prompt_count()
            return

        rubric.set_active_transfer_priority(None)
        if next_message.incomplete_priority:
            if rubric.active_incomplete_priority == next_message.incomplete_priority:
                rubric.increment_incomplete_prompt_count()
            else:
                rubric.set_active_incomplete_priority(next_message.incomplete_priority)
                rubric.reset_incomplete_prompt_count()
                rubric.increment_incomplete_prompt_count()
            return

        rubric.set_active_incomplete_priority(None)
        rubric.reset_incomplete_prompt_count()

    @staticmethod
    def _priority_prompt_for_item(priority_key: str, rubric: Rubric) -> str:
        current_error = rubric.current_scenario.error if rubric.current_scenario else ""
        error_type = DebuggingPracticeDuckWorkflow._error_type(current_error)
        priority_bucket = PRIORITY_BUCKETS[priority_key]
        return DebuggingPracticeDuckWorkflow._priority_prompt(priority_bucket, error_type)

    @staticmethod
    def _priority_prompt(prefab_bucket: str, error_type: str = "error") -> str:
        return DuckAgent._priority_prompt(prefab_bucket, error_type)

    async def _resolve_next_message(
            self,
            context: DuckContext,
            rubric: Rubric,
            assessment,
            conversation_context: list[ConversationTurn],
    ) -> NextMessage:
        if rubric.active_transfer_priority and not self._duck_agent.priority_item_understood(
                assessment,
                rubric.active_transfer_priority,
        ):
            completion = await self._duck_agent.review_concept_transfer(
                context,
                rubric,
                conversation_context,
                rubric.active_transfer_priority,
            )
            if completion.concept_understood:
                rubric.mark_priority_fulfilled(rubric.active_transfer_priority)
                updated_assessment = self._duck_agent.apply_understood_priority(
                    assessment,
                    rubric.active_transfer_priority,
                )
                return await self._duck_agent.next_message(
                    context,
                    rubric,
                    updated_assessment,
                    conversation_context,
                )
            if completion.response:
                return NextMessage(
                    completion.response,
                    False,
                    rubric.current_scenario_index,
                    rubric.active_transfer_priority,
                )
            return NextMessage(
                self._priority_prompt_for_item(rubric.active_transfer_priority, rubric),
                False,
                rubric.current_scenario_index,
                rubric.active_transfer_priority,
            )

        if rubric.active_incomplete_priority and not self._duck_agent.priority_item_understood(
                assessment,
                rubric.active_incomplete_priority,
        ):
            return await self._duck_agent.next_incomplete_subprocess_message(
                context,
                rubric,
                assessment,
                conversation_context,
                rubric.active_incomplete_priority,
                rubric.active_incomplete_prompt_count,
            )

        return await self._duck_agent.next_message(
            context,
            rubric,
            assessment,
            conversation_context,
        )

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
