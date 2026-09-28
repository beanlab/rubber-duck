"""Automatically evaluate one prompt with questioner, answerer, and evaluator agents."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "evaluation_assets" / "prompt_eval.yaml"
DEFAULT_OUTPUT = ROOT / "prompt_eval_results.json"


class StandardResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standard_id: str
    passed: bool
    evidence: str
    reason: str


class Grade(BaseModel):
    """The evaluator returns one result for every scenario standard."""

    model_config = ConfigDict(extra="forbid")

    results: list[StandardResult]


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
        return response.output_text.strip()

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


def scenario_for_questioner(scenario: dict[str, Any]) -> str:
    visible = {
        "learner": scenario["learner"],
        "task": scenario["task"],
    }
    return json.dumps(visible, indent=2)


def evaluator_input(
    scenario: dict[str, Any],
    metrics: dict[str, Any],
    question: str,
    answer: str,
) -> str:
    return json.dumps(
        {
            "scenario": scenario,
            "metrics": metrics,
            "learner_question": question,
            "tutor_answer": answer,
        },
        indent=2,
    )


def summarize(trials: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    summary = {}
    for name in metrics:
        results = [
            result
            for trial in trials
            for result in trial["standard_results"]
            if result["metric"] == name
        ]
        passed_count = sum(result["passed"] for result in results)
        summary[name] = {
            "passed_standards": passed_count,
            "total_standards": len(results),
            "pass_rate": passed_count / len(results),
            "passed": passed_count == len(results),
        }
    return {
        "metrics": summary,
        "prompt_passed": all(metric["passed"] for metric in summary.values()),
    }


def match_results_to_standards(
    grade: Grade,
    standards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected = {standard["standard_id"]: standard for standard in standards}
    returned = {result.standard_id: result for result in grade.results}
    if len(returned) != len(grade.results) or returned.keys() != expected.keys():
        raise ValueError(
            "Evaluator must return every declared standard_id exactly once; "
            f"expected {sorted(expected)}, got {sorted(returned)}"
        )

    return [
        {
            **standard,
            **returned[standard["standard_id"]].model_dump(exclude={"standard_id"}),
        }
        for standard in standards
    ]


async def evaluate(
    config: dict[str, Any],
    candidate_prompt: str,
    gateway: Any,
) -> dict[str, Any]:
    trials = []
    for scenario in config["scenarios"]:
        question = await gateway.text(
            model=config["models"]["questioner"],
            instructions=config["questioner_prompt"],
            input_text=scenario_for_questioner(scenario),
        )
        answer = await gateway.text(
            model=config["models"]["answerer"],
            instructions=candidate_prompt,
            input_text=question,
        )
        grade = await gateway.grade(
            model=config["models"]["evaluator"],
            instructions=config["evaluator_prompt"],
            input_text=evaluator_input(scenario, config["metrics"], question, answer),
        )
        standard_results = match_results_to_standards(
            grade,
            scenario["response_standard"],
        )
        trials.append(
            {
                "scenario_id": scenario["id"],
                "question": question,
                "answer": answer,
                "standard_results": standard_results,
            }
        )

    result = {
        "candidate_prompt": candidate_prompt,
        "candidate_prompt_sha256": hashlib.sha256(candidate_prompt.encode()).hexdigest(),
        "models": config["models"],
        "trials": trials,
    }
    result.update(summarize(trials, config["metrics"]))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--prompt", type=Path, help="Prompt file to evaluate instead of the YAML candidate_prompt")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


async def main() -> None:
    load_dotenv()
    args = parse_args()
    config = load_config(args.config)
    candidate_prompt = (
        args.prompt.read_text(encoding="utf-8")
        if args.prompt
        else config["candidate_prompt"]
    )
    result = await evaluate(config, candidate_prompt, OpenAIModel())
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Prompt passed: {result['prompt_passed']}")
    for name, metric in result["metrics"].items():
        print(
            f"{name}: pass_rate={metric['pass_rate']:.0%}, "
            f"passed={metric['passed']}"
        )
    print(f"Full evidence: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
