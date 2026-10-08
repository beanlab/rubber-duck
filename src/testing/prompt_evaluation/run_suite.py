"""Run Standard Duck prompt evaluation suites concurrently or with Batch API."""

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import TypeAdapter

from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.build import build_agent
from src.testing.prompt_evaluation.concurrency import map_concurrently
from src.testing.prompt_evaluation.evaluation import (
    PreparedEvaluation,
    evaluate_next_response,
    prepare_next_response,
)
from src.testing.prompt_evaluation.jev import JevEvaluator
from src.testing.prompt_evaluation.openai_batch import evaluate_openai_batch
from src.testing.prompt_evaluation.reporting import (
    print_case_evaluation,
    print_prompt_summary,
)
from src.testing.prompt_evaluation.types import (
    EvaluationCase,
    EvaluationCasesFile,
    EvaluationConfig,
    EvaluationRun,
    RubberDuckTestsConfig,
)
from src.utils.config_loader import load_configuration


Mode = Literal["live", "batch"]
ROOT = Path(__file__).resolve().parents[3]
TEST_ROOT = ROOT / "tests/tester_bot_tests/prompt_evaluation"


@dataclass(frozen=True)
class Arguments:
    mode: Mode
    concurrency: int
    poll_seconds: float
    case_id: str | None


def _load_yaml(path: Path) -> object:
    data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


async def _send_message(*_args: object, **_kwargs: object) -> int:
    return 1


async def run_suite(arguments: Arguments) -> list[EvaluationRun]:
    """Run every configured case without reusing prior responses or judgments."""
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")
    jev_key = os.getenv("JEV_API_KEY")
    if not jev_key:
        raise RuntimeError("JEV_API_KEY is required for test selection")

    shared_config = TypeAdapter(EvaluationConfig).validate_python(
        _load_yaml(TEST_ROOT / "config.yaml")
    )
    cases = TypeAdapter(EvaluationCasesFile).validate_python(
        _load_yaml(TEST_ROOT / "cases.yaml")
    )["cases"]
    if arguments.case_id is not None:
        cases = [case for case in cases if case["id"] == arguments.case_id]
        if not cases:
            raise ValueError(f"Unknown case: {arguments.case_id}")
    rubber_duck_tests = TypeAdapter(RubberDuckTestsConfig).validate_python(
        _load_yaml(TEST_ROOT / "rubber_duck_tests.yaml")
    )["rubber_duck_tests"]

    application_config = load_configuration(str(ROOT / "production-config.yaml"))
    agent = build_agent(
        application_config["ducks"]["standard-rubber-duck"]["settings"]["agent"]
    )
    armory = Armory(_send_message)
    armory.scrub_tools(TalkTool(_send_message))
    jev = JevEvaluator(
        api_key=jev_key,
        model=shared_config.get("jev_model", "jev-latest"),
    )

    async with AsyncOpenAI() as client:
        if arguments.mode == "live":
            async def evaluate(case: EvaluationCase) -> EvaluationRun:
                return await evaluate_next_response(
                    client=client,
                    config=_case_config(shared_config, case),
                    transcript=case["transcript"],
                    agent=agent,
                    armory=armory,
                    jev_evaluator=jev,
                    rubber_duck_tests=rubber_duck_tests,
                )

            results = await map_concurrently(
                cases,
                evaluate,
                limit=arguments.concurrency,
            )
        else:
            async def prepare(case: EvaluationCase) -> PreparedEvaluation:
                return await prepare_next_response(
                    client=client,
                    config=_case_config(shared_config, case),
                    transcript=case["transcript"],
                    agent=agent,
                    armory=armory,
                    jev_evaluator=jev,
                    rubber_duck_tests=rubber_duck_tests,
                )

            prepared = await map_concurrently(
                cases,
                prepare,
                limit=arguments.concurrency,
            )
            results = await evaluate_openai_batch(
                client,
                prepared,
                poll_seconds=arguments.poll_seconds,
            )

    for case, result in zip(cases, results, strict=True):
        print_case_evaluation(case, result)
    print_prompt_summary(results)
    return results


def _case_config(
    shared: EvaluationConfig,
    case: EvaluationCase,
) -> EvaluationConfig:
    config = shared.copy()
    config["reference_answer"] = case["reference_answer"]
    config["case_tests"] = case.get("tests", {})
    return config


def _parse_arguments(values: list[str]) -> Arguments:
    if not values or values[0] not in {"live", "batch"}:
        raise ValueError(
            "Usage: python -m src.testing.prompt_evaluation.run_suite "
            "<live|batch> [--concurrency N] [--poll-seconds N] [--case ID]"
        )
    mode: Mode = "live" if values[0] == "live" else "batch"
    concurrency = 3
    poll_seconds = 10.0
    case_id = None
    index = 1
    while index < len(values):
        option = values[index]
        if index + 1 >= len(values):
            raise ValueError(f"Missing value for {option}")
        value = values[index + 1]
        if option == "--concurrency":
            concurrency = int(value)
        elif option == "--poll-seconds":
            poll_seconds = float(value)
        elif option == "--case":
            case_id = value
        else:
            raise ValueError(f"Unknown option: {option}")
        index += 2
    if concurrency < 1:
        raise ValueError("Concurrency must be at least 1")
    if poll_seconds <= 0 or poll_seconds > 60:
        raise ValueError("Poll seconds must be greater than 0 and at most 60")
    return Arguments(mode, concurrency, poll_seconds, case_id)


def main() -> int:
    arguments = _parse_arguments(sys.argv[1:])
    results = asyncio.run(run_suite(arguments))
    return 0 if all(result["summary"]["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
