"""Run fresh fixed-prefix evaluations with explicit artifact recording."""

import asyncio
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import TypeAdapter

from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.build import build_agent
from src.testing.prompt_evaluation.artifacts import (
    ExperimentArtifactWriter,
    ExperimentManifest,
    TrialArtifact,
    TrialError,
    candidate_snapshot,
    current_source_commit,
    generation_observation,
)
from src.testing.prompt_evaluation.concurrency import map_concurrently
from src.testing.prompt_evaluation.evaluation import evaluate_next_response
from src.testing.prompt_evaluation.jev import JevEvaluator
from src.testing.prompt_evaluation.observation import TrialCapture
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


ROOT = Path(__file__).resolve().parents[3]
TEST_ROOT = ROOT / "tests/tester_bot_tests/prompt_evaluation"


@dataclass(frozen=True)
class Arguments:
    output_directory: Path
    repetitions: int
    concurrency: int
    case_id: str | None


@dataclass(frozen=True)
class TrialPlan:
    case: EvaluationCase
    repetition: int


@dataclass(frozen=True)
class TrialOutcome:
    case: EvaluationCase
    repetition: int
    trial_id: str
    result: EvaluationRun | None
    error: TrialError | None


def _load_yaml(path: Path) -> object:
    data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


async def _send_message(*_args: object, **_kwargs: object) -> int:
    return 1


def _case_config(
    shared: EvaluationConfig,
    case: EvaluationCase,
) -> EvaluationConfig:
    config = shared.copy()
    config["reference_answer"] = case["reference_answer"]
    config["case_tests"] = case.get("tests", {})
    return config


async def run_experiment(arguments: Arguments) -> list[TrialOutcome]:
    """Run fresh trials and persist evidence only to the requested directory."""
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
    experiment_id = str(uuid.uuid4())
    writer = ExperimentArtifactWriter(arguments.output_directory)
    writer.initialize(
        ExperimentManifest(
            experiment_id=experiment_id,
            created_at=datetime.now(timezone.utc),
            source_commit=current_source_commit(ROOT),
            repetitions=arguments.repetitions,
            concurrency=arguments.concurrency,
            candidate=candidate_snapshot(
                agent,
                [armory.get_tool_schema(name) for name in agent.tools],
            ),
            evaluation_config=shared_config,
            rubber_duck_tests=rubber_duck_tests,
            scenarios=cases,
        )
    )

    plans = [
        TrialPlan(case=case, repetition=repetition)
        for case in cases
        for repetition in range(1, arguments.repetitions + 1)
    ]
    jev = JevEvaluator(
        api_key=jev_key,
        model=shared_config.get("jev_model", "jev-latest"),
    )

    async with AsyncOpenAI() as client:

        async def evaluate(plan: TrialPlan) -> TrialOutcome:
            trial_id = str(uuid.uuid4())
            capture = TrialCapture()
            started_at = datetime.now(timezone.utc)
            started_clock = time.perf_counter()
            result: EvaluationRun | None = None
            trial_error: TrialError | None = None
            try:
                result = await evaluate_next_response(
                    client=client,
                    config=_case_config(shared_config, plan.case),
                    transcript=plan.case["transcript"],
                    agent=agent,
                    armory=armory,
                    jev_evaluator=jev,
                    rubber_duck_tests=rubber_duck_tests,
                    observer=capture,
                )
            except Exception as error:
                trial_error = TrialError(
                    type=error.__class__.__name__,
                    message=str(error),
                )

            ended_at = datetime.now(timezone.utc)
            writer.write_trial(
                TrialArtifact(
                    experiment_id=experiment_id,
                    trial_id=trial_id,
                    scenario_id=plan.case["id"],
                    repetition=plan.repetition,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_seconds=time.perf_counter() - started_clock,
                    status="completed" if trial_error is None else "failed",
                    generation=generation_observation(capture),
                    jev=(
                        capture.selection.result
                        if capture.selection is not None
                        else None
                    ),
                    evaluation=result,
                    error=trial_error,
                )
            )
            return TrialOutcome(
                case=plan.case,
                repetition=plan.repetition,
                trial_id=trial_id,
                result=result,
                error=trial_error,
            )

        outcomes = await map_concurrently(
            plans,
            evaluate,
            limit=arguments.concurrency,
        )

    completed_results: list[EvaluationRun] = []
    for outcome in outcomes:
        if outcome.result is None:
            print(
                f"Trial {outcome.trial_id} failed for {outcome.case['id']} "
                f"repetition {outcome.repetition}: {outcome.error}"
            )
            continue
        print(f"\nTrial: {outcome.trial_id} (repetition {outcome.repetition})")
        print_case_evaluation(outcome.case, outcome.result)
        completed_results.append(outcome.result)
    if completed_results:
        print_prompt_summary(completed_results)
    print(f"\nExperiment artifacts: {arguments.output_directory.resolve()}")
    return outcomes


def _parse_arguments(values: list[str]) -> Arguments:
    output_directory: Path | None = None
    repetitions = 1
    concurrency = 3
    case_id = None
    index = 0
    while index < len(values):
        option = values[index]
        if index + 1 >= len(values):
            raise ValueError(f"Missing value for {option}")
        value = values[index + 1]
        if option == "--output":
            output_directory = Path(value)
        elif option == "--repetitions":
            repetitions = int(value)
        elif option == "--concurrency":
            concurrency = int(value)
        elif option == "--case":
            case_id = value
        else:
            raise ValueError(f"Unknown option: {option}")
        index += 2

    if output_directory is None:
        raise ValueError("--output is required")
    if repetitions < 1:
        raise ValueError("Repetitions must be at least 1")
    if concurrency < 1:
        raise ValueError("Concurrency must be at least 1")
    return Arguments(output_directory, repetitions, concurrency, case_id)


def main() -> int:
    arguments = _parse_arguments(sys.argv[1:])
    outcomes = asyncio.run(run_experiment(arguments))
    return 1 if any(outcome.error is not None for outcome in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
