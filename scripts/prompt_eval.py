"""Evaluate one tutoring prompt against defined tutoring-quality criteria."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.testing.prompt_evaluation import (
    CriterionResult,
    OpenAIModel,
    PromptEvaluation,
    TutorReply,
    print_evaluation,
)


DEFAULT_CONFIG = ROOT / "evaluation_assets" / "prompt_eval.yaml"
DEFAULT_OUTPUT = ROOT / "prompt_eval_results.json"



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
