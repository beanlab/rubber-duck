"""Run fresh fixed-prefix evaluations with explicit artifact recording."""

import asyncio
import os
import re
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
from src.testing.prompt_evaluation.experiment_config import (
    ExperimentSpecification,
    load_experiment_specification,
)
from src.testing.prompt_evaluation.experiment_reporting import (
    build_experiment_summary,
    concise_console_summary,
    render_experiment_charts,
    render_experiment_report,
)
from src.testing.prompt_evaluation.jev import JevEvaluator
from src.testing.prompt_evaluation.observation import TrialCapture
from src.testing.prompt_evaluation.reporting import print_case_evaluation
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
    name: str
    output_directory: Path
    repetitions: int
    concurrency: int
    case_ids: list[str] | None
    detailed_console: bool


@dataclass(frozen=True)
class TrialPlan:
    number: int
    case: EvaluationCase
    repetition: int


@dataclass(frozen=True)
class TrialOutcome:
    case: EvaluationCase
    artifact: TrialArtifact


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
    cases = _select_cases(cases, arguments.case_ids)
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
    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        name=arguments.name,
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
    writer.initialize(manifest)

    plans = [
        TrialPlan(number=index, case=case, repetition=repetition)
        for index, (case, repetition) in enumerate(
            (
                (case, repetition)
                for case in cases
                for repetition in range(1, arguments.repetitions + 1)
            ),
            start=1,
        )
    ]
    jev = JevEvaluator(
        api_key=jev_key,
        model=shared_config.get("jev_model", "jev-latest"),
    )

    print(f"Experiment: {arguments.name}", flush=True)
    print(f"Output: {arguments.output_directory.resolve()}", flush=True)
    print(
        f"Running {len(plans)} fresh trials with concurrency "
        f"{arguments.concurrency}\n",
        flush=True,
    )
    completed_count = 0
    progress_lock = asyncio.Lock()

    async with AsyncOpenAI() as client:
        async def evaluate(plan: TrialPlan) -> TrialOutcome:
            nonlocal completed_count
            print(
                f"[{plan.number}/{len(plans)}] START {plan.case['id']} — "
                f"repetition {plan.repetition}",
                flush=True,
            )
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
            artifact = TrialArtifact(
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
            writer.write_trial(artifact)
            async with progress_lock:
                completed_count += 1
                progress = completed_count
            print(
                f"[{progress}/{len(plans)}] DONE {plan.case['id']} — "
                f"repetition {plan.repetition} — {_trial_console_result(artifact)} "
                f"— {artifact.duration_seconds:.1f}s",
                flush=True,
            )
            if arguments.detailed_console and result is not None:
                print_case_evaluation(plan.case, result)
            return TrialOutcome(case=plan.case, artifact=artifact)

        outcomes = await map_concurrently(
            plans,
            evaluate,
            limit=arguments.concurrency,
        )

    artifacts = [outcome.artifact for outcome in outcomes]
    summary = build_experiment_summary(manifest, artifacts)
    writer.write_charts(render_experiment_charts(manifest, artifacts, summary))
    report_path = writer.write_report(
        render_experiment_report(manifest, artifacts, summary)
    )
    summary_path = writer.write_summary(summary)
    print()
    for line in concise_console_summary(summary):
        print(line)
    print(f"  Readable report:           {report_path.resolve()}")
    print(f"  Machine summary:           {summary_path.resolve()}")
    return outcomes


def _parse_arguments(values: list[str]) -> Arguments:
    if not values:
        raise ValueError(
            "Usage: ./experiment <experiment.yaml> or ./experiment --output <dir>"
        )
    if len(values) == 1 and not values[0].startswith("--"):
        return _arguments_from_specification(Path(values[0]))

    output_directory: Path | None = None
    repetitions = 1
    concurrency = 3
    case_id: str | None = None
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
    return Arguments(
        name="ad-hoc-experiment",
        output_directory=output_directory,
        repetitions=repetitions,
        concurrency=concurrency,
        case_ids=[case_id] if case_id is not None else None,
        detailed_console=False,
    )


def _arguments_from_specification(path: Path) -> Arguments:
    specification = load_experiment_specification(path)
    output_directory = _output_directory(specification)
    case_ids = None if specification.cases == "all" else specification.cases
    return Arguments(
        name=specification.name,
        output_directory=output_directory,
        repetitions=specification.repetitions,
        concurrency=specification.concurrency,
        case_ids=case_ids,
        detailed_console=specification.reporting.console == "detailed",
    )


def _output_directory(specification: ExperimentSpecification) -> Path:
    if specification.output_directory is not None:
        path = specification.output_directory
        return path if path.is_absolute() else ROOT / path
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", specification.name).strip("-")
    if not safe_name:
        safe_name = "experiment"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return ROOT / "experiments/runs" / f"{timestamp}-{safe_name}-{suffix}"


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


def _trial_console_result(artifact: TrialArtifact) -> str:
    if artifact.error is not None:
        return f"ERROR ({artifact.error.type})"
    if artifact.evaluation is None:
        return "INCOMPLETE"
    if artifact.evaluation["summary"]["passed"]:
        return "PASS"
    failed = ", ".join(artifact.evaluation["summary"]["blocking_tests"])
    return f"FAIL ({failed})"


def main() -> int:
    try:
        arguments = _parse_arguments(sys.argv[1:])
    except (OSError, ValueError) as error:
        print(f"Experiment configuration error: {error}", file=sys.stderr)
        return 2
    outcomes = asyncio.run(run_experiment(arguments))
    return 1 if any(outcome.artifact.error is not None for outcome in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
