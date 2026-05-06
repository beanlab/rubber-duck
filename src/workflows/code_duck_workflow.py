from pathlib import Path
from typing import Any

from quest import step
import yaml

from ..gen_ai.gen_ai import Agent, AIClient
from ..utils.config_types import CodeDuckSettings, DuckContext
from ..utils.message_utils import wait_for_message
from ..utils.protocols import ConversationComplete


ConversationTurn = tuple[str, str]


def _review_turns(settings: dict[str, Any]):
    review_turns = settings.get("review_turns", 5)
    if review_turns == "full":
        return iter(int, 1)
    return range(review_turns)


class CodeDuckWorkflow:
    def __init__(
            self,
            name: str,
            send_message,
            settings: CodeDuckSettings,
            conversation_review_agent: Agent,
            ai_client: AIClient,
    ):
        self.name = name
        self._send_message = step(send_message)
        self._settings = settings
        self._conversation_review_agent = conversation_review_agent
        self._ai_client = ai_client
        self._conversation_review_agent.output_format = None

    async def __call__(self, context: DuckContext):
        try:
            conversation_context: list[ConversationTurn] = []
            rubric = await self._load_rubric()
            full_project = self._full_project(rubric)

            opening_message = self._opening_message(full_project)
            conversation_context.append(("Student", opening_message))
            await self._send_message(context.thread_id, opening_message)
            user_response = await self._wait_for_user_response(context)

            for _ in _review_turns(self._settings):
                conversation_context.append(("TA", user_response))

                code_duck_message = await self._review_conversation(
                    context,
                    rubric,
                    full_project,
                    conversation_context,
                )

                if not code_duck_message:
                    return

                conversation_context.append(("Student", code_duck_message))
                await self._send_message(context.thread_id, code_duck_message)

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
            conversation_context: list[ConversationTurn],
    ) -> str:
        analysis_context = self._analysis_context(rubric, full_project, conversation_context)
        raw_response = await self._ai_client.run_agent(context, self._conversation_review_agent, analysis_context)
        return raw_response.strip() if raw_response else ""

    def _first_message(self) -> str:
        return self._settings["first_message"]

    def _opening_message(self, full_project: str) -> str:
        first_message = self._first_message().strip()
        if not full_project.strip():
            return first_message
        return f"{first_message}\n\n```python\n{full_project.strip()}\n```"

    @staticmethod
    def _full_project(rubric: dict[str, Any]) -> str:
        full_project = rubric.get("full project", "")
        if isinstance(full_project, str):
            return full_project
        if full_project:
            return yaml.safe_dump(full_project)
        return ""

    @staticmethod
    def _analysis_context(
            rubric: dict[str, Any],
            full_project: str,
            conversation_context: list[ConversationTurn],
    ) -> str:
        rubric_text = yaml.safe_dump(rubric, sort_keys=False).strip()
        conversation = "\n\n".join(
            f"{speaker}: {message.strip()}"
            for speaker, message in conversation_context
        )
        return "\n\n".join([
            "Rubric and traceback scenarios:",
            rubric_text,
            "Current full project:",
            f"```python\n{full_project.strip()}\n```",
            "Conversation:",
            conversation,
        ])
