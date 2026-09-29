"""Evaluate one tutoring prompt against three defined metrics."""

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

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


class MetricResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    reason: str


class PromptEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correctness: MetricResult
    guidance: MetricResult
    disclosure: MetricResult


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
        config: dict,
    ) -> PromptEvaluation:
        evidence = {
            "transcript": transcript,
            "reference_answer": config["reference_answer"],
            "allowed_help": config["allowed_help"],
            "metrics": config["metrics"],
        }
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
        model,
        config["evaluator_prompt"],
        transcript,
        config,
    )
    metrics = evaluation.model_dump()

    return {
        "transcript": transcript,
        "metrics": metrics,
        "prompt_passed": all(result["passed"] for result in metrics.values()),
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


async def main():
    load_dotenv()
    args = parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    result = await run(config, OpenAIModel())
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print("\nEvaluation:")
    print(f"Prompt passed: {result['prompt_passed']}")
    for metric, value in result["metrics"].items():
        print(f"{metric}: passed={value['passed']} — {value['reason']}")
    print(f"Transcript and results: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
