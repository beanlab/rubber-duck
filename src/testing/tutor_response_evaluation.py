"""Generate and evaluate one tutor response after a fixed conversation prefix."""

import json
from typing import Any, Generic, Literal, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict


TUTOR_TOOLS = [
    {
        "type": "function",
        "name": "talk_to_user",
        "description": "Send a message to the student and wait for a reply.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"message_to_user": {"type": "string"}},
            "required": ["message_to_user"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "conclude_conversation",
        "description": "End the conversation.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
]


Rating = TypeVar("Rating", bound=str)

SubjectAccuracy = Literal[
    "incorrect", "partially_correct", "correct", "insufficient_evidence"
]
MisconceptionDiagnosis = Literal[
    "misses",
    "partially_recognizes",
    "accurately_recognizes",
    "not_applicable",
    "insufficient_evidence",
]
GuidanceScaffolding = Literal[
    "harmful_or_absent",
    "weak",
    "useful",
    "especially_effective",
    "insufficient_evidence",
]
AnswerDisclosure = Literal[
    "prohibited", "excessive", "appropriate", "not_applicable", "insufficient_evidence"
]
Relevance = Literal["irrelevant", "partly_relevant", "relevant", "insufficient_evidence"]
Actionability = Literal[
    "no_next_step", "vague", "actionable", "not_applicable", "insufficient_evidence"
]


class CriterionResult(BaseModel, Generic[Rating]):
    model_config = ConfigDict(extra="forbid")

    rating: Rating
    evidence: list[str]
    rationale: str


class PromptEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_accuracy: CriterionResult[SubjectAccuracy]
    misconception_diagnosis: CriterionResult[MisconceptionDiagnosis]
    guidance_scaffolding: CriterionResult[GuidanceScaffolding]
    answer_disclosure: CriterionResult[AnswerDisclosure]
    relevance: CriterionResult[Relevance]
    actionability: CriterionResult[Actionability]


def build_tutor_history(transcript: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert student/tutor turns into the tool history used by the tutor."""
    history: list[dict[str, Any]] = []
    pending_call_id: str | None = None

    for index, turn in enumerate(transcript, start=1):
        role = turn["role"]
        message = turn["message"]
        if role == "student":
            if pending_call_id is None:
                history.append({"role": "user", "content": message})
            else:
                history.append(
                    {
                        "type": "function_call_output",
                        "call_id": pending_call_id,
                        "output": message,
                    }
                )
                pending_call_id = None
            continue

        if role != "tutor":
            raise ValueError(f"Unsupported transcript role: {role}")
        if pending_call_id is not None:
            raise ValueError("Tutor turns must be followed by a student turn")

        pending_call_id = f"prefix_call_{index}"
        history.append(
            {
                "type": "function_call",
                "call_id": pending_call_id,
                "name": "talk_to_user",
                "arguments": json.dumps({"message_to_user": message}),
            }
        )

    if pending_call_id is not None:
        raise ValueError("A prefix must end with a student message")
    return history


def _response_message(response: Any) -> str:
    calls = [item for item in response.output if item.type == "function_call"]
    if len(calls) > 1:
        raise RuntimeError("Tutor returned more than one action")

    if calls:
        call = calls[0]
        if call.name == "conclude_conversation":
            return "[conversation concluded]"
        if call.name != "talk_to_user":
            raise RuntimeError(f"Unsupported tutor tool: {call.name}")
        message = json.loads(call.arguments)["message_to_user"].strip()
    else:
        message = response.output_text.strip()

    if not message:
        raise RuntimeError("Tutor returned an empty message")
    return message


async def evaluate_next_response(
    *,
    client: AsyncOpenAI,
    config: dict,
    transcript: list[dict[str, str]],
    tutor_prompt: str,
) -> dict:
    """Generate and evaluate exactly one tutor response after a fixed prefix."""
    tutor_response = await client.responses.create(
        model=config["model"],
        instructions=tutor_prompt,
        input=build_tutor_history(transcript),
        tools=TUTOR_TOOLS,
        tool_choice="auto",
        include=["reasoning.encrypted_content"],
        store=False,
    )
    candidate_response = {
        "role": "tutor",
        "message": _response_message(tutor_response),
    }
    evaluator_input: dict[str, Any] = {
        "conversation_prefix": transcript,
        "candidate_response": candidate_response,
        "tutor_prompt": tutor_prompt,
        "criteria": config["criteria"],
    }
    if config.get("use_reference_answer", True) and config.get("reference_answer"):
        evaluator_input["reference_answer"] = config["reference_answer"]

    evaluation_response = await client.responses.parse(
        model=config.get("evaluator_model", config["model"]),
        instructions=config["evaluator_prompt"],
        input=json.dumps(evaluator_input, indent=2),
        text_format=PromptEvaluation,
        store=False,
    )
    if evaluation_response.output_parsed is None:
        raise RuntimeError("Evaluator returned no result")

    return {
        "transcript": [*transcript, candidate_response],
        "criteria": evaluation_response.output_parsed.model_dump(),
        "reference_answer_used": "reference_answer" in evaluator_input,
    }


def print_evaluation(result: dict) -> None:
    print("\nEvaluation:")
    for criterion, value in result["criteria"].items():
        name = criterion.replace("_", " ").title()
        grade = value["rating"].replace("_", " ").upper()
        print(f"\n{name}: {grade}")
        print(f"  Explanation: {value['rationale']}")
