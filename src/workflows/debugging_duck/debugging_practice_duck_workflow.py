import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict
from quest import step, task
import yaml

from ...gen_ai.gen_ai import AIClient, Agent
from ...utils.config_types import DebuggingPracticeDuckSettings, DuckContext
from ...utils.protocols import ConversationComplete
from .conversation import DebuggingConversation
from .messaging import MessageRouting


PRIORITY_ORDER = ["concept", "location", "intent", "fix"]
AssessmentStatus = Literal[
    "complete",
    "incorrect",
    "incomplete",
    "unattempted",
    "related",
    "unrelated",
]


@lru_cache(maxsize=1)
def load_debugging_practice_responses() -> dict[str, list[str]]:
    responses_path = (
        Path(__file__).parents[2]
        / "prompts"
        / "debugging-practice-duck"
        / "prefabs.yaml"
    )
    with responses_path.open(encoding="utf-8") as prefab_file:
        responses = yaml.safe_load(prefab_file) or {}
    return {
        key: value
        for key, value in responses.items()
        if isinstance(value, list)
    }


def load_rubric_files(settings: dict[str, Any]) -> dict[str, Any]:
    rubric_files = settings["rubric_path"]
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


def build_rubric_state(rubric_data: dict[str, Any]) -> dict[str, Any]:
    exercises = []

    project_fields = {"full project", "code", "correct code"}
    exercise_names = [
        name
        for name in rubric_data
        if name not in project_fields
    ]

    for name in exercise_names:
        rubric_item = rubric_data[name]
        traceback = "\n".join(rubric_item["traceback"]).strip()
        code = rubric_item.get("code")

        if isinstance(code, list):
            code = "\n".join(str(item).strip()
                             for item in code if str(item).strip())
        elif code is None:
            code = ""
        else:
            code = str(code).strip()

        exercise = {
            "name": str(name),
            "rubric_text": yaml.safe_dump(
                {name: rubric_item},
                sort_keys=False,
            ).strip(),
            "traceback": traceback,
            "error_type": error_type(traceback),
            "code": code,
        }

        exercises.append(exercise)

    return {
        "exercises": exercises,
        "text": yaml.safe_dump(rubric_data, sort_keys=False).strip(),
    }


def error_type(traceback: str) -> str:
    for line in reversed(traceback.splitlines()):
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


def conversation_context_text(conversation: DebuggingConversation) -> str:
    role_map = {
        conversation.duck_actor: "Student",
        conversation.user_actor: "TA",
    }
    return "\n\n".join(
        f"{role_map.get(actor, actor)}: {content}"
        for actor, content in conversation.items
        if content
    )


def exercise_complete(status: dict[str, AssessmentStatus]) -> bool:
    all_priorities_complete = all(
        status.get(priority_key) == "complete"
        for priority_key in PRIORITY_ORDER
    )
    concept_and_fix_complete = (
        status.get("concept") == "complete"
        and status.get("fix") == "complete"
    )
    return all_priorities_complete or concept_and_fix_complete


class GeneralAssessor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    status: AssessmentStatus


class SubprocessCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    response: str


class DebuggingPracticeDuckWorkflow:
    def __init__(
            self,
            name: str,
            send_message,
            settings: DebuggingPracticeDuckSettings,
            ai_client: AIClient,
            assessor_agents: dict[str, Agent],
            incomplete_subprocess: Agent | None = None,
            incorrect_subprocess: Agent | None = None,
            unrelated_subprocess: Agent | None = None,
    ):
        self.name = name
        self._send_message = send_message
        self._settings = settings
        self._assessor_agents = assessor_agents
        self._ai_client = ai_client
        self._incomplete_agent = incomplete_subprocess
        self._incorrect_agent = incorrect_subprocess
        self._unrelated_agent = unrelated_subprocess

    @task
    async def _run_assessor(
            self,
            context: DuckContext,
            priority_key: str,
            prompt: str,
    ) -> GeneralAssessor:
        result = await self._ai_client.run_agent(
            context,
            self._assessor_agents[priority_key],
            prompt,
            output_format=GeneralAssessor,
        )
        return cast(GeneralAssessor, result)

    @step
    async def _run_assessors(
            self,
            context: DuckContext,
            rubric: dict[str, Any],
            exercise: dict[str, Any],
            conversation: DebuggingConversation,
            goal: str,
    ) -> dict[str, AssessmentStatus]:
        conversation_context = conversation_context_text(conversation)
        output_contract = json.dumps(
            GeneralAssessor.model_json_schema(),
            indent=2,
        ).strip()

        priority_assessments = [
            self._run_assessor(
                context,
                priority_key,
                self._assessor_agents[priority_key].prompt.format(
                    output_contract=output_contract,
                    exercise_rubric_item=exercise["rubric_text"],
                    conversation_context=conversation_context,
                ),
            )
            for priority_key in PRIORITY_ORDER
        ]
        unrelated_prompt = self._assessor_agents["unrelated"].prompt.format(
            output_contract=output_contract,
            assessment_rubric=rubric["text"],
            conversation_context=conversation_context,
        )

        unrelated_assessment_task = self._run_assessor(
            context,
            "unrelated",
            unrelated_prompt,
        )
        priority_results = [
            await priority_assessment
            for priority_assessment in priority_assessments
        ]
        unrelated_assessment = await unrelated_assessment_task
        priority_status: dict[str, AssessmentStatus] = {
            priority_key: cast(GeneralAssessor, priority_results[index]).status
            for index, priority_key in enumerate(PRIORITY_ORDER)
        }
        if unrelated_assessment.status == "unrelated":
            priority_status[goal] = "unrelated"
        print(
            f"DEBUG assessor statuses for goal={goal}: "
            f"priority={priority_status}, unrelated={unrelated_assessment.status}"
        )
        return priority_status

    @step
    async def _run_completion_subprocess(
            self,
            context: DuckContext,
            exercise: dict[str, Any],
            conversation: DebuggingConversation,
            agent: Agent,
            priority_key: str | None = None,
    ) -> SubprocessCompletion:
        conversation_context = conversation_context_text(conversation)
        output_contract = json.dumps(
            SubprocessCompletion.model_json_schema(),
            indent=2,
        ).strip()
        rendered_prompt = agent.prompt.format(
            output_contract=output_contract,
            exercise_rubric_item=exercise["rubric_text"],
            conversation_context=conversation_context,
            active_priority=priority_key or "none",
            priority_topic=priority_key or "",
        )
        result = await self._ai_client.run_agent(
            context,
            agent,
            rendered_prompt,
            output_format=SubprocessCompletion,
        )
        return cast(SubprocessCompletion, result)

    def _compose_exercise_context_message(
            self,
            exercise: dict[str, Any],
            completed_previous: bool = False,
    ) -> str:
        responses = load_debugging_practice_responses()
        message_parts = [
            " ".join([
                random.choice(responses["item_complete"]),
                random.choice(responses["next_item"]),
            ])
            if completed_previous
            else "Here is the code and its associated error.",
        ]
        if exercise["code"]:
            message_parts.extend([
                "Code:",
                f"```python\n{exercise['code'].strip()}\n```",
            ])
        if exercise["traceback"]:
            message_parts.extend([
                "Traceback:",
                f"```\n{exercise['traceback']}\n```",
            ])
        return "\n\n".join(message_parts)

    @step
    async def _build_incomplete_response_message(
            self,
            context: DuckContext,
            exercise: dict[str, Any],
            conversation: DebuggingConversation,
            priority_key: str,
    ) -> str:
        completion = await self._run_completion_subprocess(
            context,
            exercise,
            conversation,
            self._incomplete_agent,
            priority_key=priority_key,
        )
        response = completion.response.strip()
        if response:
            return response

        responses = load_debugging_practice_responses()
        return random.choice(responses["retry_incomplete"])

    @step
    async def _build_unrelated_completion_message(
            self,
            context: DuckContext,
            exercise: dict[str, Any],
            conversation: DebuggingConversation,
    ) -> str:
        completion = await self._run_completion_subprocess(
            context,
            exercise,
            conversation,
            self._unrelated_agent,
        )
        response = completion.response.strip()
        if response:
            return response

        responses = load_debugging_practice_responses()
        return random.choice(responses["retry_fix"])

    @step
    async def _build_incorrect_response_message(
            self,
            context: DuckContext,
            exercise: dict[str, Any],
            conversation: DebuggingConversation,
            priority_key: str,
    ) -> str:
        completion = await self._run_completion_subprocess(
            context,
            exercise,
            conversation,
            self._incorrect_agent,
            priority_key=priority_key,
        )
        response = completion.response.strip()
        if response:
            return response

        responses = load_debugging_practice_responses()
        return random.choice(responses[priority_key]).format(
            error_type=exercise["error_type"],
        )

    async def __call__(self, context: DuckContext):
        conversation = DebuggingConversation()
        routing = MessageRouting(context, self._send_message)

        try:
            loaded_rubric = load_rubric_files(self._settings)
            rubric = build_rubric_state(loaded_rubric)
            conversation.append_duck(
                await routing.send(f"*{self._settings['first_message'].strip()}*"),
            )

            for exercise_index, exercise in enumerate(rubric["exercises"]):
                message = self._compose_exercise_context_message(
                    exercise,
                    completed_previous=exercise_index > 0,
                )
                conversation.append_duck(await routing.send(message))

                status: dict[str, AssessmentStatus] = {
                    priority_key: "unattempted"
                    for priority_key in PRIORITY_ORDER
                }

                for goal in PRIORITY_ORDER:
                    if exercise_complete(status):
                        break

                    grace = 1

                    while status[goal] != "complete":
                        responses = load_debugging_practice_responses()
                        if status[goal] == "unattempted":
                            response = random.choice(responses[goal]).format(
                                error_type=exercise["error_type"],
                            )

                        elif status[goal] == "unrelated":
                            response = await self._build_unrelated_completion_message(
                                context,
                                exercise,
                                conversation,
                            )

                        elif status[goal] == "incomplete" and grace:
                            grace -= 1
                            response = await self._build_incomplete_response_message(
                                context,
                                exercise,
                                conversation,
                                goal,
                            )

                        elif status[goal] == "incorrect" or (
                            status[goal] == "incomplete" and not grace
                        ):
                            response = await self._build_incorrect_response_message(
                                context,
                                exercise,
                                conversation,
                                goal,
                            )

                        else:
                            raise ValueError(
                                f"Unsupported assessment status: {status[goal]}")

                        conversation.append_duck(await routing.send(response))
                        conversation.append_user(await routing.wait())

                        status = await self._run_assessors(
                            context,
                            rubric,
                            exercise,
                            conversation,
                            goal,
                        )

            responses = load_debugging_practice_responses()
            complete_message = random.choice(responses["exercise_complete"])
            conversation.append_duck(await routing.send(complete_message))
            await routing.send(self._settings["feedback_message"])

        except ConversationComplete as error:
            if str(error):
                conversation.append_duck(await routing.send(str(error)))
