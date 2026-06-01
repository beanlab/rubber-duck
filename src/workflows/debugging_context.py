from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
import yaml

from .debugging_parsing import schema_prompt_text


ConversationTurn = tuple[str, str]
AgentContextType = Literal[
    "incomplete_response",
    "unrelated_completion",
    "incorrect_response",
]


class AssessorPromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_contract: str
    exercise_rubric_item: str
    assessment_rubric: str
    conversation_context: str


class CompletionPromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_contract: str
    exercise_rubric_item: str
    conversation_context: str
    active_priority: str
    priority_topic: str


def record_student_message(
        conversation_context: list[ConversationTurn],
        response: str,
) -> None:
    conversation_context.append(("Student", response))


def record_ta_message(
        conversation_context: list[ConversationTurn],
        response: str,
) -> None:
    conversation_context.append(("TA", response))


def exercise_text(exercise: dict[str, Any]) -> str:
    return yaml.safe_dump(
        {
            "name": exercise["name"],
            "rubric_item": exercise["rubric_item"],
            "traceback": exercise["error"],
            "code": exercise["code"],
            "error line": exercise["error_line"],
            "intended behavior": exercise["intended_behavior"],
            "required fix": exercise["required_fix"],
            "required concept": exercise["required_concept"],
        },
        sort_keys=False,
    ).strip()


def conversation_text(conversation_context: list[ConversationTurn]) -> str:
    return "\n\n".join(
        f"{speaker}: {message.strip()}"
        for speaker, message in conversation_context
    )


def rubric_text(rubric: dict[str, Any]) -> str:
    return yaml.safe_dump(
        {
            "full project": rubric["full_project"],
            "exercises": rubric["exercises"],
        },
        sort_keys=False,
    ).strip()


def render_completion_prompt(
        prompt: str,
        agent_type: AgentContextType,
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
        priority_key: str | None = None,
) -> str:
    if agent_type == "incorrect_response" and priority_key is None:
        raise ValueError("incorrect_response prompt requires priority_key")

    prompt_context = CompletionPromptContext.model_validate({
        "output_contract": schema_prompt_text(agent_type),
        "exercise_rubric_item": exercise_text(exercise),
        "conversation_context": conversation_text(conversation_context),
        "active_priority": priority_key or "none",
        "priority_topic": priority_key or "",
    })
    return prompt.format(**prompt_context.model_dump())


def render_assessor_prompt(
        prompt: str,
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
        schema_name: str,
        rubric: dict[str, Any] | None = None,
) -> str:
    prompt_context = AssessorPromptContext.model_validate({
        "output_contract": schema_prompt_text(schema_name),
        "exercise_rubric_item": exercise_text(exercise),
        "assessment_rubric": rubric_text(rubric) if rubric else "",
        "conversation_context": conversation_text(conversation_context),
    })
    return prompt.format(**prompt_context.model_dump())
