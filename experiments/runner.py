"""Run a YAML-configured tutor experiment sequentially."""

import asyncio
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from experiments.config import (
    ExperimentSpecification,
    load_experiment_specification,
)
from experiments.results import (
    Candidate,
    ExperimentResults,
    TrialError,
    TrialResult,
    source_commit,
    write_results,
)
from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.build import build_agent
from src.gen_ai.decision import JevDecisionService
from src.utils.config_loader import load_configuration
from tests.prompt_evaluation.config import (
    case_configuration,
    load_evaluation_suite,
)
from tests.prompt_evaluation.evaluation import evaluate_next_response
from tests.prompt_evaluation.reporting import print_case_evaluation
from tests.prompt_evaluation.selection import CriterionDecisionEvaluator
from tests.prompt_evaluation.types import EvaluationCase


ROOT = Path(__file__).resolve().parents[1]
SUITE_DIRECTORY = ROOT / "tests/prompt_evaluation"


async def _send_message(*_args: object, **_kwargs: object) -> int:
    return 1


async def run_experiment(
    specification: ExperimentSpecification,
) -> tuple[ExperimentResults, Path]:
    load_dotenv()
    openai_key = os.getenv("OPENAI_API_KEY")
    jev_key = os.getenv("JEV_API_KEY")
    if not openai_key or not jev_key:
        raise RuntimeError("OPENAI_API_KEY and JEV_API_KEY are required")

    suite = load_evaluation_suite(SUITE_DIRECTORY)
    cases = _select_cases(
        suite.cases,
        None if specification.cases == "all" else specification.cases,
    )
    application_config = load_configuration(str(ROOT / "production-config.yaml"))
    agent = build_agent(
        application_config["ducks"]["standard-rubber-duck"]["settings"]["agent"]
    )
    armory = Armory(_send_message)
    armory.scrub_tools(TalkTool(_send_message))
    selector = CriterionDecisionEvaluator(
        JevDecisionService(
            api_key=jev_key,
            model=suite.config.get("jev_model", "jev-latest"),
        )
    )
    trials: list[TrialResult] = []

    async with AsyncOpenAI(api_key=openai_key) as client:
        for case in cases:
            for repetition in range(1, specification.repetitions + 1):
                started = time.perf_counter()
                evaluation = None
                error = None
                try:
                    evaluation = await evaluate_next_response(
                        client=client,
                        config=case_configuration(suite.config, case),
                        transcript=case["transcript"],
                        agent=agent,
                        armory=armory,
                        jev_evaluator=selector,
                        rubber_duck_tests=suite.rubber_duck_tests,
                    )
                    print_case_evaluation(case, evaluation)
                except Exception as exception:
                    error = TrialError(
                        type=exception.__class__.__name__,
                        message=str(exception),
                    )
                    print(f"\n{case['id']} repetition {repetition}: ERROR {error.message}")
                trials.append(
                    TrialResult(
                        case_id=case["id"],
                        repetition=repetition,
                        duration_seconds=time.perf_counter() - started,
                        evaluation=evaluation,
                        error=error,
                    )
                )

    results = ExperimentResults(
        name=specification.name,
        created_at=datetime.now(timezone.utc),
        source_commit=source_commit(ROOT),
        repetitions=specification.repetitions,
        candidate=Candidate(
            name=agent.name,
            prompt=agent.prompt,
            model=agent.model,
            tools=list(agent.tools),
            reasoning=agent.reasoning,
        ),
        trials=trials,
    )
    result_path = write_results(_output_directory(specification), results)
    print(f"\nResults: {result_path}")
    return results, result_path


def _select_cases(
    available: list[EvaluationCase],
    selected_ids: list[str] | None,
) -> list[EvaluationCase]:
    if selected_ids is None:
        return available
    by_id = {case["id"]: case for case in available}
    unknown = [case_id for case_id in selected_ids if case_id not in by_id]
    if unknown:
        raise ValueError(f"Unknown cases: {unknown}")
    return [by_id[case_id] for case_id in selected_ids]


def _output_directory(specification: ExperimentSpecification) -> Path:
    if specification.output_directory is not None:
        path = specification.output_directory
        return path if path.is_absolute() else ROOT / path
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", specification.name).strip("-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return ROOT / "experiments/results" / f"{timestamp}-{safe_name or 'experiment'}"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: ./experiments/run <experiment.yaml>", file=sys.stderr)
        return 2
    try:
        specification = load_experiment_specification(Path(sys.argv[1]))
        results, _ = asyncio.run(run_experiment(specification))
    except (OSError, RuntimeError, ValueError) as exception:
        print(f"Experiment error: {exception}", file=sys.stderr)
        return 2
    return 1 if any(trial.error is not None for trial in results.trials) else 0


if __name__ == "__main__":
    raise SystemExit(main())
