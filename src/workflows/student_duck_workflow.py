import json
from pathlib import Path
from typing import Any

import yaml
from quest import step

from ..gen_ai.gen_ai import Agent, AIClient
from ..armory.tools import register_tool
from ..utils.config_types import DuckContext, StudentDuckSettings
from ..utils.message_utils import wait_for_message
from ..utils.protocols import ConversationComplete


CheckResult = dict[str, str]
ConversationTurn = dict[str, Any]
DEFAULT_FIRST_MESSAGE = "What are we going to learn today?"


def _check_output_format(check_type: str) -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": f"student_duck_{check_type}_check",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "check_type": {
                        "type": "string",
                        "enum": [check_type],
                    },
                    "assessment": {
                        "type": "string",
                    },
                },
                "required": ["check_type", "assessment"],
                "additionalProperties": False,
            },
        },
    }


class StudentDuckRubricTools:
    def __init__(self, settings: StudentDuckSettings):
        rubric_roots = settings.get("rubric_roots", settings.get("rubric_root", "rubrics"))
        if isinstance(rubric_roots, str):
            rubric_roots = [rubric_roots]

        self._rubric_roots = [Path(root).resolve() for root in rubric_roots]
        self._selected_rubrics: dict[int, tuple[str, dict[str, Any]]] = {}

    def get_selected_rubric(self, thread_id: int) -> tuple[str, dict[str, Any]] | None:
        return self._selected_rubrics.get(thread_id)

    def get_catalog(self) -> list[dict[str, str]]:
        return [
            {
                "rubric_id": rubric_id,
                "path": str(path),
                "description": self._rubric_description(rubric),
            }
            for rubric_id, path, rubric in self._iter_rubrics()
        ]

    @register_tool
    async def select_student_duck_rubric(self, ctx: DuckContext, subject: str, topic: str) -> str:
        """
        Select and load the best available student-duck rubric for a subject and topic.
        Returns JSON with selected, rubric_id, description, and available_rubrics fields.
        """
        matches = self._rank_rubrics(subject, topic)
        if not matches:
            return json.dumps({
                "selected": False,
                "rubric_id": "",
                "description": "No available rubric matched the requested subject and topic.",
                "available_rubrics": self.get_catalog(),
            })

        _, rubric_id, _, rubric = matches[0]
        self._selected_rubrics[ctx.thread_id] = (rubric_id, rubric)
        return json.dumps({
            "selected": True,
            "rubric_id": rubric_id,
            "description": self._rubric_description(rubric),
            "available_rubrics": self.get_catalog(),
        })

    def _rank_rubrics(self, subject: str, topic: str) -> list[tuple[int, str, Path, dict[str, Any]]]:
        search_terms = self._search_terms(f"{subject} {topic}")
        matches: list[tuple[int, str, Path, dict[str, Any]]] = []

        for rubric_id, path, rubric in self._iter_rubrics():
            searchable_text = " ".join([
                rubric_id,
                path.stem,
                json.dumps(rubric),
            ]).lower()
            score = sum(1 for term in search_terms if term in searchable_text)
            if score:
                matches.append((score, rubric_id, path, rubric))

        return sorted(matches, key=lambda match: (-match[0], match[1]))

    def _iter_rubrics(self):
        for root in self._rubric_roots:
            if not root.exists():
                continue

            for path in sorted(root.rglob("*.yaml")):
                if not self._is_allowed_path(root, path):
                    continue

                file_contents = path.read_text()
                if not file_contents.strip():
                    continue

                parsed = yaml.safe_load(file_contents)
                if not isinstance(parsed, dict):
                    continue

                yield self._rubric_id(root, path), path, parsed

    @staticmethod
    def _is_allowed_path(root: Path, path: Path) -> bool:
        try:
            path.resolve().relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _rubric_id(root: Path, path: Path) -> str:
        return path.resolve().relative_to(root).with_suffix("").as_posix()

    @staticmethod
    def _rubric_description(rubric: dict[str, Any]) -> str:
        for key in ("description", "title", "name"):
            value = rubric.get(key)
            if isinstance(value, str):
                return value
        return ""

    @staticmethod
    def _search_terms(text: str) -> list[str]:
        return [
            term.lower()
            for term in text.replace("/", " ").replace("-", " ").replace("_", " ").split()
            if len(term) > 1
        ]


class StudentDuckWorkflow:
    def __init__(
            self,
            name: str,
            send_message,
            settings: StudentDuckSettings,
            student_agent: Agent,
            error_checker_agent: Agent,
            omission_checker_agent: Agent,
            ai_client: AIClient,
            rubric_tools: StudentDuckRubricTools | None = None,
    ):
        self.name = name
        self._send_message = step(send_message)
        self._settings = settings
        self._student_agent = student_agent
        self._error_checker_agent = error_checker_agent
        self._omission_checker_agent = omission_checker_agent
        self._ai_client = ai_client
        self._rubric_tools = rubric_tools
        self._error_checker_agent.output_format = _check_output_format("error")
        self._omission_checker_agent.output_format = _check_output_format("omission")

    async def __call__(self, context: DuckContext):
        try:
            conversation_context: list[ConversationTurn] = []

            await self._send_message(context.thread_id, self._first_message())
            user_response = await self._wait_for_user_response(context)

            max_review_turns = self._settings.get("max_review_turns", 5)
            for _ in range(max_review_turns):
                rubric = await self._load_rubric(context)
                user_turn: ConversationTurn = {"role": "user", "content": user_response}
                conversation_context.append(user_turn)

                error_review = await self._check_for_errors(
                    context,
                    user_response,
                    rubric,
                    conversation_context,
                )
                omission_review = await self._check_for_omissions(
                    context,
                    user_response,
                    rubric,
                    conversation_context,
                )

                user_turn["checks"] = [error_review, omission_review]

                student_message = await self._ask_as_student(
                    context,
                    user_response,
                    error_review,
                    omission_review,
                    rubric,
                    conversation_context,
                )

                if not student_message:
                    return

                conversation_context.append({"role": "assistant", "content": student_message})
                await self._send_message(context.thread_id, student_message)

                user_response = await self._wait_for_user_response(context)

        except ConversationComplete as error:
            if str(error):
                await self._send_message(context.thread_id, str(error))
                return

    @step
    async def _load_rubric(self, context: DuckContext) -> dict[str, Any]:
        selected_rubric = self._rubric_tools.get_selected_rubric(context.thread_id) if self._rubric_tools else None
        if selected_rubric:
            _, rubric = selected_rubric
            return rubric

        rubric_files = self._settings.get("rubric_path", [])
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

    def _first_message(self) -> str:
        return self._settings.get("first_message", DEFAULT_FIRST_MESSAGE)

    async def _check_for_errors(
            self,
            context: DuckContext,
            user_response: str,
            rubric: dict[str, Any],
            conversation_context: list[ConversationTurn],
    ) -> CheckResult:
        payload = {
            "rubric": rubric,
            "user_response": user_response,
            "conversation_context": conversation_context,
        }
        raw_response = await self._ai_client.run_agent(context, self._error_checker_agent, json.dumps(payload))
        return self._parse_check_result(raw_response, "error")

    async def _check_for_omissions(
            self,
            context: DuckContext,
            user_response: str,
            rubric: dict[str, Any],
            conversation_context: list[ConversationTurn],
    ) -> CheckResult:
        payload = {
            "rubric": rubric,
            "user_response": user_response,
            "conversation_context": conversation_context,
        }
        raw_response = await self._ai_client.run_agent(context, self._omission_checker_agent, json.dumps(payload))
        return self._parse_check_result(raw_response, "omission")

    @staticmethod
    def _parse_check_result(raw_response: str | None, expected_check_type: str) -> CheckResult:
        if not raw_response:
            return {
                "check_type": expected_check_type,
                "assessment": "",
            }

        result = json.loads(raw_response)
        return {
            "check_type": result.get("check_type", expected_check_type),
            "assessment": result.get("assessment", ""),
        }

    async def _ask_as_student(
            self,
            context: DuckContext,
            user_response: str,
            error_review: CheckResult,
            omission_review: CheckResult,
            rubric: dict[str, Any],
            conversation_context: list[ConversationTurn],
    ) -> str | None:
        payload = {
            "rubric": rubric,
            "selected_rubric_id": self._selected_rubric_id(context),
            "available_rubrics": self._available_rubrics(),
            "user_response": user_response,
            "current_checks": [error_review, omission_review],
            "conversation_context": conversation_context,
        }
        return await self._ai_client.run_agent(context, self._student_agent, json.dumps(payload))

    def _selected_rubric_id(self, context: DuckContext) -> str | None:
        selected_rubric = self._rubric_tools.get_selected_rubric(context.thread_id) if self._rubric_tools else None
        if not selected_rubric:
            return None
        rubric_id, _ = selected_rubric
        return rubric_id

    def _available_rubrics(self) -> list[dict[str, str]]:
        if not self._rubric_tools:
            return []
        return self._rubric_tools.get_catalog()
