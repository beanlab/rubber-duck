"""Evaluate a tutoring prompt through complete simulated conversations."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
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
        "description": "Send a message to the learner and wait for their reply.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "message_to_user": {"type": "string"},
            },
            "required": ["message_to_user"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "conclude_conversation",
        "description": "End the tutoring conversation.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
]


class StandardResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standard_id: str
    passed: bool
    evidence_turns: list[int]
    evidence_quote: str
    reason: str


class Grade(BaseModel):
    """One evaluator result for every declared conversation standard."""

    model_config = ConfigDict(extra="forbid")

    results: list[StandardResult]


@dataclass(frozen=True)
class TutorAction:
    kind: Literal["message", "conclude"]
    message: str | None
    response_items: list[dict[str, Any]]
    call_id: str | None = None


class OpenAIModel:
    """The only provider-specific code in the evaluator."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI()

    async def text(self, *, model: str, instructions: str, input_text: str) -> str:
        response = await self.client.responses.create(
            model=model,
            instructions=instructions,
            input=input_text,
            store=False,
        )
        text = response.output_text.strip()
        if not text:
            raise RuntimeError("Student simulator returned no message")
        return text

    async def tutor(
        self,
        *,
        model: str,
        instructions: str,
        input_items: list[dict[str, Any]],
    ) -> TutorAction:
        response = await self.client.responses.create(
            model=model,
            instructions=instructions,
            input=input_items,
            tools=TUTOR_TOOLS,
            tool_choice="auto",
            include=["reasoning.encrypted_content"],
            store=False,
        )
        response_items = [
            item.model_dump(mode="json", exclude_none=True)
            for item in response.output
        ]
        calls = [item for item in response.output if item.type == "function_call"]
        if len(calls) > 1:
            raise RuntimeError("Tutor returned multiple conversation actions")
        if calls:
            call = calls[0]
            arguments = json.loads(call.arguments)
            if call.name == "talk_to_user":
                message = arguments["message_to_user"].strip()
                if not message:
                    raise RuntimeError("Tutor called talk_to_user with no message")
                return TutorAction("message", message, response_items, call.call_id)
            if call.name == "conclude_conversation":
                return TutorAction("conclude", None, response_items, call.call_id)
            raise RuntimeError(f"Tutor called unsupported tool: {call.name}")

        message = response.output_text.strip()
        if not message:
            raise RuntimeError("Tutor returned neither a message nor a conversation tool")
        return TutorAction("message", message, response_items)

    async def grade(self, *, model: str, instructions: str, input_text: str) -> Grade:
        response = await self.client.responses.parse(
            model=model,
            instructions=instructions,
            input=input_text,
            text_format=Grade,
            store=False,
        )
        if response.output_parsed is None:
            raise RuntimeError("Evaluator did not return a grade")
        return response.output_parsed


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_candidate_prompt(config: dict[str, Any], override: Path | None) -> str:
    path = override or ROOT / config["candidate_prompt_path"]
    return path.read_text(encoding="utf-8")


def student_input(
    scenario: dict[str, Any],
    transcript: list[dict[str, Any]],
) -> str:
    student_scenario = {
        key: scenario[key]
        for key in (
            "id",
            "learner",
            "task",
            "student_script",
            "completion_message",
        )
    }
    return json.dumps(
        {"scenario": student_scenario, "transcript": transcript},
        indent=2,
    )


def evaluator_input(
    scenario: dict[str, Any],
    metrics: dict[str, Any],
    transcript: list[dict[str, Any]],
    stop_reason: str,
) -> str:
    return json.dumps(
        {
            "scenario": scenario,
            "metrics": metrics,
            "transcript": transcript,
            "stop_reason": stop_reason,
        },
        indent=2,
    )


async def simulate_conversation(
    config: dict[str, Any],
    scenario: dict[str, Any],
    candidate_prompt: str,
    gateway: Any,
) -> tuple[list[dict[str, Any]], str]:
    transcript: list[dict[str, Any]] = []
    tutor_history: list[dict[str, Any]] = []
    pending_call_id: str | None = None

    student_message = await gateway.text(
        model=config["models"]["student"],
        instructions=config["student_prompt"],
        input_text=student_input(scenario, transcript),
    )
    transcript.append(
        {"turn": 1, "role": "student", "action": "message", "content": student_message}
    )

    stop_reason = "max_tutor_turns"
    for tutor_turn in range(scenario["max_tutor_turns"]):
        if pending_call_id:
            tutor_history.append(
                {
                    "type": "function_call_output",
                    "call_id": pending_call_id,
                    "output": student_message,
                }
            )
        else:
            tutor_history.append({"role": "user", "content": student_message})

        action = await gateway.tutor(
            model=config["models"]["tutor"],
            instructions=candidate_prompt,
            input_items=tutor_history,
        )
        tutor_history.extend(action.response_items)

        if action.kind == "conclude":
            transcript.append(
                {
                    "turn": len(transcript) + 1,
                    "role": "tutor",
                    "action": "conclude_conversation",
                    "content": "",
                }
            )
            stop_reason = "tutor_concluded"
            break

        transcript.append(
            {
                "turn": len(transcript) + 1,
                "role": "tutor",
                "action": "message",
                "content": action.message,
            }
        )
        if tutor_turn + 1 == scenario["max_tutor_turns"]:
            break

        student_message = await gateway.text(
            model=config["models"]["student"],
            instructions=config["student_prompt"],
            input_text=student_input(scenario, transcript),
        )
        transcript.append(
            {
                "turn": len(transcript) + 1,
                "role": "student",
                "action": "message",
                "content": student_message,
            }
        )
        pending_call_id = action.call_id

    return transcript, stop_reason


def match_results_to_standards(
    grade: Grade,
    standards: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected = {standard["standard_id"]: standard for standard in standards}
    returned = {result.standard_id: result for result in grade.results}
    if len(returned) != len(grade.results) or returned.keys() != expected.keys():
        raise ValueError(
            "Evaluator must return every declared standard_id exactly once; "
            f"expected {sorted(expected)}, got {sorted(returned)}"
        )

    turns = {item["turn"]: item["content"] for item in transcript}
    for result in grade.results:
        if any(turn not in turns for turn in result.evidence_turns):
            raise ValueError(f"Evaluator cited an unknown transcript turn: {result.standard_id}")
        if result.evidence_quote != "none":
            cited_text = "\n".join(turns[turn] for turn in result.evidence_turns)
            if result.evidence_quote not in cited_text:
                raise ValueError(
                    f"Evaluator quote is absent from cited turns: {result.standard_id}"
                )

    return [
        {
            **standard,
            **returned[standard["standard_id"]].model_dump(exclude={"standard_id"}),
        }
        for standard in standards
    ]


def summarize(
    conversations: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    metric_summary = {}
    for name in metrics:
        results = [
            result
            for conversation in conversations
            for result in conversation["standard_results"]
            if result["metric"] == name
        ]
        if not results:
            continue
        passed_count = sum(result["passed"] for result in results)
        metric_summary[name] = {
            "passed_standards": passed_count,
            "total_standards": len(results),
            "pass_rate": passed_count / len(results),
            "passed": passed_count == len(results),
        }

    return {
        "metrics": metric_summary,
        "prompt_passed": all(metric["passed"] for metric in metric_summary.values()),
    }


async def evaluate(
    config: dict[str, Any],
    candidate_prompt: str,
    gateway: Any,
) -> dict[str, Any]:
    conversations = []
    for scenario in config["scenarios"]:
        transcript, stop_reason = await simulate_conversation(
            config,
            scenario,
            candidate_prompt,
            gateway,
        )
        grade = await gateway.grade(
            model=config["models"]["evaluator"],
            instructions=config["evaluator_prompt"],
            input_text=evaluator_input(
                scenario,
                config["metrics"],
                transcript,
                stop_reason,
            ),
        )
        standard_results = match_results_to_standards(
            grade,
            scenario["conversation_standard"],
            transcript,
        )
        conversations.append(
            {
                "scenario_id": scenario["id"],
                "stop_reason": stop_reason,
                "passed": all(result["passed"] for result in standard_results),
                "transcript": transcript,
                "standard_results": standard_results,
            }
        )

    result = {
        "candidate_prompt": candidate_prompt,
        "candidate_prompt_sha256": hashlib.sha256(candidate_prompt.encode()).hexdigest(),
        "models": config["models"],
        "conversations": conversations,
    }
    result.update(summarize(conversations, config["metrics"]))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--prompt", type=Path, help="Prompt file to evaluate")
    parser.add_argument(
        "--scenario",
        action="append",
        help="Scenario ID to run; repeat for multiple scenarios",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


async def main() -> None:
    load_dotenv()
    args = parse_args()
    config = load_config(args.config)
    if args.scenario:
        selected = set(args.scenario)
        config["scenarios"] = [
            scenario for scenario in config["scenarios"] if scenario["id"] in selected
        ]
        found = {scenario["id"] for scenario in config["scenarios"]}
        if found != selected:
            raise ValueError(f"Unknown scenario IDs: {sorted(selected - found)}")

    candidate_prompt = load_candidate_prompt(config, args.prompt)
    result = await evaluate(config, candidate_prompt, OpenAIModel())
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Prompt passed: {result['prompt_passed']}")
    for conversation in result["conversations"]:
        print(
            f"{conversation['scenario_id']}: passed={conversation['passed']}, "
            f"stop={conversation['stop_reason']}"
        )
    for name, metric in result["metrics"].items():
        print(
            f"{name}: pass_rate={metric['pass_rate']:.0%}, "
            f"passed={metric['passed']}"
        )
    print(f"Full transcripts and evidence: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
