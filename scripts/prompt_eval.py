"""Evaluate one tutoring prompt against defined tutoring-quality criteria."""

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "evaluation_assets" / "prompt_eval.yaml"
DEFAULT_OUTPUT = ROOT / "prompt_eval_results.json"

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
    def __init__(self):
        self.client = AsyncOpenAI()

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
                message = json.loads(call.arguments)["message_to_user"]
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
        evidence = {
            "transcript": transcript,
            "tutor_prompt": tutor_prompt,
            "criteria": config["criteria"],
        }
        if config.get("use_reference_answer", True):
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


async def run(config: dict, model_client: Any) -> dict:
    model = config["model"]
    evaluator_model = config.get("evaluator_model", model)
    tutor_prompt = (ROOT / config["prompt_path"]).read_text(encoding="utf-8")
    transcript = []
    tutor_history = []
    pending_tutor_call = None

    student_message = await model_client.student(
        model,
        config["student_prompt"],
        transcript,
    )
    transcript.append({"role": "student", "message": student_message})
    print("\nConversation:", flush=True)
    print(f"\nStudent: {student_message}", flush=True)

    for _ in range(config["max_tutor_turns"]):
        if pending_tutor_call:
            tutor_history.append(
                {
                    "type": "function_call_output",
                    "call_id": pending_tutor_call,
                    "output": student_message,
                }
            )
        else:
            tutor_history.append({"role": "user", "content": student_message})

        tutor_reply = await model_client.tutor(model, tutor_prompt, tutor_history)
        tutor_history.extend(tutor_reply.api_items)

        if tutor_reply.action == "conclude":
            transcript.append({"role": "tutor", "message": "[conversation concluded]"})
            print("\nTutor: [conversation concluded]", flush=True)
            break

        transcript.append({"role": "tutor", "message": tutor_reply.message})
        print(f"\nTutor: {tutor_reply.message}", flush=True)
        student_message = await model_client.student(
            model,
            config["student_prompt"],
            transcript,
        )
        transcript.append({"role": "student", "message": student_message})
        print(f"\nStudent: {student_message}", flush=True)
        pending_tutor_call = tutor_reply.call_id

    evaluation = await model_client.grade(
        evaluator_model,
        config["evaluator_prompt"],
        transcript,
        tutor_prompt,
        config,
    )
    criteria = evaluation.model_dump()

    return {
        "transcript": transcript,
        "criteria": criteria,
        "reference_answer_used": config.get("use_reference_answer", True),
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=["1"],
        help="Student prompt numbers to run, or 'all'",
    )
    parser.add_argument(
        "--no-reference-answer",
        action="store_true",
        help="Evaluate without giving the evaluator the reference answer",
    )
    return parser.parse_args()


def select_prompts(catalog: dict, requested: list[str]) -> list[tuple[str, dict]]:
    if requested == ["all"]:
        return list(catalog.items())
    if "all" in requested:
        raise ValueError("Use 'all' by itself")

    unknown = [prompt_id for prompt_id in requested if prompt_id not in catalog]
    if unknown:
        raise ValueError(f"Unknown student prompt(s): {', '.join(unknown)}")
    return [(prompt_id, catalog[prompt_id]) for prompt_id in requested]


def print_evaluation(result: dict):
    print("\nEvaluation:")
    for criterion, value in result["criteria"].items():
        name = criterion.replace("_", " ").title()
        grade = value["rating"].replace("_", " ").upper()
        print(f"\n{name}: {grade}")
        print(f"  Explanation: {value['rationale']}")


async def main():
    load_dotenv()
    args = parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config["use_reference_answer"] = not args.no_reference_answer
    catalog_path = ROOT / config["student_prompts_path"]
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))["prompts"]
    selected = select_prompts(catalog, args.prompts)

    results = []
    model_client = OpenAIModel()
    for prompt_id, student_config in selected:
        print(f"\n=== Student prompt {prompt_id}: {student_config['name']} ===")
        result = await run({**config, **student_config}, model_client)
        result["student_prompt"] = {
            "id": prompt_id,
            "name": student_config["name"],
        }
        results.append(result)
        print_evaluation(result)

    args.output.write_text(
        json.dumps({"results": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Transcript and results: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
