"""Run the no-network prompt evaluator vertical slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.evaluation.adapters import RecordedResponseRunner
from src.evaluation.artifacts import ArtifactStore
from src.evaluation.comparison import compare_candidates
from src.evaluation.grading import EvidenceIntegrityGrader
from src.evaluation.reporting import write_reports
from src.evaluation.schemas import (
    EvidenceReference,
    Observation,
    ObservationStatus,
    OfflineFixture,
    digest_json,
    digest_text,
)


def load_fixture(path: Path) -> OfflineFixture:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"fixture is not valid JSON: {path}") from error
    return OfflineFixture.model_validate(raw)


def run_offline_fixture(fixture: OfflineFixture, output_root: Path) -> tuple[Path, Path]:
    declaration = fixture.declaration
    run_root = output_root / declaration.run_id
    store = ArtifactStore(run_root / "artifacts")
    store.put(
        "declarations",
        declaration.run_id,
        declaration,
        producer="prompt-eval-cli",
    )

    criteria = {item.criterion_id: item for item in declaration.criteria}
    cases = {
        (item.candidate_id, item.scenario_id, item.repetition): item
        for item in fixture.cases
    }
    runner = RecordedResponseRunner(
        declaration=declaration,
        responses={key: item.response for key, item in cases.items()},
    )
    integrity_grader = EvidenceIntegrityGrader(declaration)

    trials = []
    comparison_observations = []
    actual_order = 0
    for scenario in declaration.scenarios:
        for repetition in range(1, declaration.policy.repetitions + 1):
            for candidate in declaration.candidates:
                actual_order += 1
                trial = runner.run(
                    candidate,
                    scenario,
                    repetition=repetition,
                    planned_order=actual_order,
                    actual_order=actual_order,
                )
                trials.append(trial)
                store.put(
                    "trials",
                    trial.trial_id,
                    trial,
                    producer="recorded-runner",
                    sensitivity=trial.sensitivity,
                    parent_artifact_ids=(declaration.run_id,),
                )

                integrity = integrity_grader.grade(trial)
                store.put(
                    "observations",
                    integrity.observation_id,
                    integrity,
                    producer=integrity.grader_id,
                    sensitivity=trial.sensitivity,
                    parent_artifact_ids=(trial.trial_id,),
                )

                case = cases[(candidate.candidate_id, scenario.scenario_id, repetition)]
                for criterion_id, rating in case.ratings.items():
                    criterion = criteria[criterion_id]
                    response = trial.projected_response or ""
                    observation_id = (
                        "obs-"
                        + digest_json(
                            {
                                "trial_id": trial.trial_id,
                                "criterion_id": criterion_id,
                                "grader_id": "manual-fixture",
                            }
                        )[:24]
                    )
                    observation = Observation(
                        observation_id=observation_id,
                        run_id=declaration.run_id,
                        trial_id=trial.trial_id,
                        candidate_id=candidate.candidate_id,
                        scenario_id=scenario.scenario_id,
                        source_family_id=scenario.source_family_id,
                        repetition=repetition,
                        criterion_id=criterion_id,
                        grader_id="manual-fixture",
                        grader_version="1",
                        value_type=criterion.value_type,
                        value=rating,
                        status=ObservationStatus.OBSERVED,
                        evidence=(
                            EvidenceReference(
                                artifact_id=trial.trial_id,
                                field_path="projected_response",
                                start=0,
                                end=len(response),
                                quoted_text=response,
                                content_digest=digest_text(response),
                            ),
                        ),
                        rationale="Development-only synthetic fixture label.",
                    )
                    comparison_observations.append(observation)
                    store.put(
                        "observations",
                        observation.observation_id,
                        observation,
                        producer=observation.grader_id,
                        sensitivity=trial.sensitivity,
                        parent_artifact_ids=(trial.trial_id,),
                    )

    summary = compare_candidates(
        declaration,
        comparison_observations,
        trials=trials,
    )
    store.put(
        "comparisons",
        declaration.run_id,
        summary,
        producer="paired-comparison",
        parent_artifact_ids=tuple(trial.trial_id for trial in trials),
    )
    return write_reports(summary, run_root / "reports")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    offline = subparsers.add_parser(
        "offline",
        help="run a strict JSON fixture without model or Discord access",
    )
    offline.add_argument("--fixture", type=Path, required=True)
    offline.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "offline":
        fixture = load_fixture(args.fixture)
        json_path, markdown_path = run_offline_fixture(fixture, args.output)
        print(f"JSON report: {json_path}")
        print(f"Markdown report: {markdown_path}")
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
