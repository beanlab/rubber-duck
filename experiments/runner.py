"""Run a YAML-configured tutor experiment sequentially."""

import asyncio
import os
import re
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from typesafe_sdk import AsyncTypeSafeClient

from experiments.config import (
    ExperimentSpecification,
    load_experiment_specification,
)
from experiments.utils.results import (
    Candidate,
    ExperimentResults,
    TrialError,
    TrialResult,
    source_commit,
    write_results,
)
from experiments.utils.report import concise_console_summary, write_report
from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.build import build_agent
from src.gen_ai.jev_responses import JevAPI
from src.utils.config_loader import load_configuration
from experiments.evaluation.config import (
    case_configuration,
    load_evaluation_suite,
)
from experiments.evaluation.engine import evaluate_next_response
from experiments.evaluation.selection import CriterionDecisionEvaluator
from experiments.evaluation.types import EvaluationCase, EvaluationConfig, EvaluationRun
from src.gen_ai.gen_ai import Agent


ROOT = Path(__file__).resolve().parents[1]
PROMPT_CONFIG_DIRECTORY = ROOT / "tests/prompt_tests/configs"
USAGE = """Usage: ./experiments/run <experiment-name-or-path>

Each YAML file defines one experiment. Run a config by name:
  ./experiments/run standard-duck-baseline

Complete config reference:
  experiments/configs/README.md
"""


async def _send_message(*_args: object, **_kwargs: object) -> int:
    return 1


def _configure_models(
    specification: ExperimentSpecification,
    agent: Agent,
    evaluation_config: EvaluationConfig,
) -> tuple[Agent, EvaluationConfig, str]:
    configured_evaluation = evaluation_config.copy()
    configured_evaluation["evaluator_model"] = specification.models.evaluator
    configured_evaluation["jev_model"] = specification.models.jev
    configured_agent = replace(agent, model=specification.models.response)
    return configured_agent, configured_evaluation, specification.models.jev


async def run_experiment(
    specification: ExperimentSpecification,
) -> tuple[ExperimentResults, Path]:
    load_dotenv()
    openai_key = os.getenv("OPENAI_API_KEY")
    jev_key = os.getenv("JEV_API_KEY")
    if not openai_key or not jev_key:
        raise RuntimeError("OPENAI_API_KEY and JEV_API_KEY are required")

    suite = load_evaluation_suite(PROMPT_CONFIG_DIRECTORY)
    cases = _select_cases(
        suite.cases,
        None if specification.cases == "all" else specification.cases,
    )
    application_config = load_configuration(str(ROOT / "production-config.yaml"))
    agent, evaluation_config, jev_model = _configure_models(
        specification,
        build_agent(
            application_config["ducks"]["standard-rubber-duck"]["settings"]["agent"]
        ),
        suite.config,
    )
    armory = Armory(_send_message)
    armory.scrub_tools(TalkTool(_send_message))
    trials: list[TrialResult] = []
    total_trials = len(cases) * specification.repetitions

    print(f"Experiment: {specification.name}", flush=True)
    print(f"Running {total_trials} trials\n", flush=True)

    async with (
        AsyncOpenAI(api_key=openai_key) as client,
        AsyncTypeSafeClient(api_key=jev_key) as jev_client,
    ):
        selector = CriterionDecisionEvaluator(
            JevAPI(jev_client),
            model=jev_model,
        )
        for case in cases:
            for repetition in range(1, specification.repetitions + 1):
                trial_number = len(trials) + 1
                print(
                    f"[{trial_number}/{total_trials}] START {case['id']} — "
                    f"repetition {repetition}",
                    flush=True,
                )
                started = time.perf_counter()
                evaluation = None
                error = None
                try:
                    evaluation = await evaluate_next_response(
                        client=client,
                        config=case_configuration(evaluation_config, case),
                        transcript=case["transcript"],
                        agent=agent,
                        armory=armory,
                        jev_evaluator=selector,
                        rubber_duck_tests=suite.rubber_duck_tests,
                    )
                except Exception as exception:
                    error = TrialError(
                        type=exception.__class__.__name__,
                        message=str(exception),
                    )
                duration_seconds = time.perf_counter() - started
                trials.append(
                    TrialResult(
                        case_id=case["id"],
                        case_name=case["name"],
                        repetition=repetition,
                        duration_seconds=duration_seconds,
                        evaluation=evaluation,
                        error=error,
                    )
                )
                print(
                    f"[{trial_number}/{total_trials}] DONE {case['id']} — "
                    f"repetition {repetition} — "
                    f"{_trial_console_result(evaluation, error)} — "
                    f"{duration_seconds:.1f}s",
                    flush=True,
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
    report_path = write_report(result_path.parent, results)
    print()
    for line in concise_console_summary(results):
        print(line)
    print(f"  Readable report: {report_path}")
    print(f"  Complete results: {result_path}")
    return results, result_path


async def run_recorded_experiment(
    specification: ExperimentSpecification,
) -> tuple[ExperimentResults, Path]:
    """Run an experiment inside the Quest context required by stepped APIs."""
    from quest import Historian, NoopSerializer

    history: list[object] = []
    historian = Historian(
        workflow_id=f"experiment:{specification.name}",
        workflow=run_experiment,
        history=history,
        serializer=NoopSerializer(),
    )
    return await historian.run(specification)


def _trial_console_result(
    evaluation: EvaluationRun | None,
    error: TrialError | None,
) -> str:
    if error is not None:
        return f"ERROR ({error.type})"
    if evaluation is None:
        return "INCOMPLETE"
    if evaluation["summary"]["passed"]:
        return "PASS"
    failed = ", ".join(evaluation["summary"]["blocking_tests"])
    return f"FAIL ({failed})"


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


def _specification_path(value: str) -> Path:
    path = Path(value)
    if path.suffix or path.parent != Path("."):
        return path
    return ROOT / "experiments/configs" / f"{value}.yaml"


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print(USAGE)
        return 0
    if len(sys.argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        specification = load_experiment_specification(_specification_path(sys.argv[1]))
        results, _ = asyncio.run(run_recorded_experiment(specification))
    except (OSError, RuntimeError, ValueError) as exception:
        print(f"Experiment error: {exception}", file=sys.stderr)
        return 2
    return 1 if any(trial.error is not None for trial in results.trials) else 0


if __name__ == "__main__":
    raise SystemExit(main())
