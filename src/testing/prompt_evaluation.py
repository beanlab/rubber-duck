"""Shared one-response tutoring prompt evaluation."""

import json
from dataclasses import dataclass
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
    "harmful_or_absent", "weak", "useful", "especially_effective", "insufficient_evidence"
]
AnswerDisclosure = Literal[
    "prohibited", "excessive", "appropriate", "not_applicable", "insufficient_evidence"
]
Relevance = Literal["irrelevant", "partly_relevant", "relevant", "insufficient_evidence"]
Actionability = Literal[
    "no_next_step", "vague", "actionable", "not_applicable", "insufficient_evidence"
]
LearnerSelfCorrection = Literal[
    "not_demonstrated",
    "partially_demonstrated",
    "demonstrated",
    "insufficient_evidence",
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
    learner_self_correction: CriterionResult[LearnerSelfCorrection]


@dataclass
class TutorReply:
    action: Literal["message", "conclude"]
    message: str | None
    api_items: list[dict[str, Any]]
    call_id: str | None


class OpenAIModel:
    def __init__(self, client: AsyncOpenAI | None = None):
        self.client = client or AsyncOpenAI()

    async def student(self, model: str, prompt: str, transcript: list[dict]) -> str:
        response = await self.client.responses.create(
            model=model,
            instructions=prompt,
            input=json.dumps({"transcript": transcript}),
            store=False,
        )
        return response.output_text.strip()

    async def tutor(self, model: str, prompt: str, history: list[dict]) -> TutorReply:
        response = await self.client.responses.create(
            model=model,
            instructions=prompt,
            input=history,
            tools=TUTOR_TOOLS,
            tool_choice="auto",
            include=["reasoning.encrypted_content"],
            store=False,
        )
        api_items = [
            item.model_dump(mode="json", exclude_none=True)
            for item in response.output
        ]
        calls = [item for item in response.output if item.type == "function_call"]

        if len(calls) > 1:
            raise RuntimeError("Tutor returned more than one action")

        if calls:
            call = calls[0]
            if call.name == "conclude_conversation":
                return TutorReply("conclude", None, api_items, call.call_id)
            if call.name == "talk_to_user":
                message = json.loads(call.arguments)["message_to_user"].strip()
                if not message:
                    raise RuntimeError("Tutor returned an empty message")
                return TutorReply("message", message, api_items, call.call_id)
            raise RuntimeError(f"Unsupported tutor tool: {call.name}")

        message = response.output_text.strip()
        if not message:
            raise RuntimeError("Tutor returned no message")
        return TutorReply("message", message, api_items, None)

    async def grade(
        self,
        model: str,
        prompt: str,
        transcript: list[dict],
        tutor_prompt: str,
        config: dict,
    ) -> PromptEvaluation:
        evidence: dict[str, Any] = {
            "tutor_prompt": tutor_prompt,
            "criteria": config["criteria"],
        }
        if config.get("evaluation_scope") == "response":
            evidence["conversation_prefix"] = transcript[:-1]
            evidence["candidate_response"] = transcript[-1]
            prompt += """

For this response-level evaluation, grade only candidate_response. Use
conversation_prefix to understand the learner's state and the evidence already
available, but do not credit or penalize candidate_response for earlier tutor
turns. No learner turn occurs after candidate_response; do not infer a later
self-correction.
"""
        else:
            evidence["transcript"] = transcript
        if config.get("use_reference_answer", True) and config.get("reference_answer"):
            evidence["reference_answer"] = config["reference_answer"]
        response = await self.client.responses.parse(
            model=model,
            instructions=prompt,
            input=json.dumps(evidence, indent=2),
            text_format=PromptEvaluation,
            store=False,
        )
        if response.output_parsed is None:
            raise RuntimeError("Evaluator returned no result")
        return response.output_parsed


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


async def evaluate_transcript(
    *,
    config: dict,
    model_client: Any,
    transcript: list[dict[str, str]],
    tutor_prompt: str,
) -> dict:
    evaluation = await model_client.grade(
        config.get("evaluator_model", config["model"]),
        config["evaluator_prompt"],
        transcript,
        tutor_prompt,
        config,
    )
    return {
        "transcript": transcript,
        "criteria": evaluation.model_dump(),
        "reference_answer_used": bool(
            config.get("use_reference_answer", True)
            and config.get("reference_answer")
        ),
    }


async def evaluate_next_response(
    *,
    config: dict,
    model_client: Any,
    transcript: list[dict[str, str]],
    tutor_prompt: str,
) -> dict:
    """Generate and evaluate exactly one tutor response after a fixed prefix."""
    tutor_reply = await model_client.tutor(
        config["model"],
        tutor_prompt,
        build_tutor_history(transcript),
    )
    response = (
        tutor_reply.message
        if tutor_reply.action == "message"
        else "[conversation concluded]"
    )
    response_config = {**config, "evaluation_scope": "response"}
    return await evaluate_transcript(
        config=response_config,
        model_client=model_client,
        transcript=[*transcript, {"role": "tutor", "message": response}],
        tutor_prompt=tutor_prompt,
    )


def print_evaluation(result: dict) -> None:
    print("\nEvaluation:")
    for criterion, value in result["criteria"].items():
        name = criterion.replace("_", " ").title()
        grade = value["rating"].replace("_", " ").upper()
        print(f"\n{name}: {grade}")
        print(f"  Explanation: {value['rationale']}")
