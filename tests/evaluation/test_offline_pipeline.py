import json

import pytest

from scripts.prompt_eval import run_offline_fixture
from src.evaluation.adapters import RecordedResponseRunner
from src.evaluation.artifacts import ArtifactExistsError, ArtifactStore
from src.evaluation.comparison import compare_candidates
from src.evaluation.grading import EvidenceIntegrityGrader, validate_evidence_span
from src.evaluation.reporting import render_markdown_report
from src.evaluation.schemas import (
    ComparisonDecision,
    ComparisonSummary,
    Observation,
    ObservationStatus,
)


def test_offline_smoke_fixture_runs_end_to_end(tmp_path, smoke_fixture):
    json_path, markdown_path = run_offline_fixture(smoke_fixture, tmp_path)

    summary = json.loads(json_path.read_text(encoding="utf-8"))
    report = markdown_path.read_text(encoding="utf-8")
    assert summary["decision"] == "inconclusive"
    assert summary["scenario_count"] == 2
    assert summary["trial_count"] == 4
    assert [item["candidate_a_better"] for item in summary["results"]] == [2, 1, 2]
    assert "Recorded responses do not establish prompt causality" in report
    assert "3/4 + 1/4" not in report
    assert "range only contains 0" not in report

    store = ArtifactStore(tmp_path / smoke_fixture.declaration.run_id / "artifacts")
    assert len(store.list_ids("trials")) == 4
    assert len(store.list_ids("observations")) == 16


def test_no_effect_fixture_reports_only_ties(tmp_path, no_effect_fixture):
    json_path, _ = run_offline_fixture(no_effect_fixture, tmp_path)
    summary = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["decision"] == "inconclusive"
    assert all(item["ties"] == 1 for item in summary["results"])
    assert all(item["candidate_a_better"] == 0 for item in summary["results"])
    assert all(item["candidate_b_better"] == 0 for item in summary["results"])


def test_standard_report_escapes_declaration_markup(tmp_path, no_effect_fixture):
    json_path, _ = run_offline_fixture(no_effect_fixture, tmp_path)
    raw_summary = json.loads(json_path.read_text(encoding="utf-8"))
    summary = ComparisonSummary.model_validate(raw_summary).model_copy(
        update={"question": "<script>alert('x')</script>\nsecond line"}
    )

    report = render_markdown_report(summary)

    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "second line" in report


def test_rerun_does_not_overwrite_evidence(tmp_path, smoke_fixture):
    run_offline_fixture(smoke_fixture, tmp_path)

    with pytest.raises(ArtifactExistsError):
        run_offline_fixture(smoke_fixture, tmp_path)


def test_recorded_trial_is_noncausal_and_citations_are_exact(smoke_fixture):
    declaration = smoke_fixture.declaration
    case = smoke_fixture.cases[0]
    runner = RecordedResponseRunner(
        declaration=declaration,
        responses={
            (case.candidate_id, case.scenario_id, case.repetition): case.response
        },
    )
    trial = runner.run(
        declaration.candidates[0],
        declaration.scenarios[0],
        repetition=1,
        planned_order=1,
        actual_order=1,
    )
    observation = EvidenceIntegrityGrader(declaration).grade(trial)

    assert trial.causal_source == "recorded"
    assert observation.value is True
    assert validate_evidence_span(trial, observation.evidence[0])
    changed = observation.evidence[0].model_copy(update={"quoted_text": "changed"})
    assert not validate_evidence_span(trial, changed)


def test_integrity_grader_detects_request_prompt_mismatch(smoke_fixture):
    declaration = smoke_fixture.declaration
    case = smoke_fixture.cases[0]
    runner = RecordedResponseRunner(
        declaration=declaration,
        responses={
            (case.candidate_id, case.scenario_id, case.repetition): case.response
        },
    )
    trial = runner.run(
        declaration.candidates[0],
        declaration.scenarios[0],
        repetition=1,
        planned_order=1,
        actual_order=1,
    )
    tampered_request = trial.request.model_copy(
        update={"instructions": "A different prompt was sent."}
    )
    tampered_trial = trial.model_copy(update={"request": tampered_request})

    observation = EvidenceIntegrityGrader(declaration).grade(tampered_trial)

    assert observation.value is False
    assert "resolved prompt" in observation.rationale


def test_comparison_with_missing_candidate_pairs_is_invalid(smoke_fixture):
    declaration = smoke_fixture.declaration
    case = smoke_fixture.cases[0]
    runner = RecordedResponseRunner(
        declaration=declaration,
        responses={
            (case.candidate_id, case.scenario_id, case.repetition): case.response
        },
    )
    trial = runner.run(
        declaration.candidates[0],
        declaration.scenarios[0],
        repetition=1,
        planned_order=1,
        actual_order=1,
    )
    observation = Observation(
        observation_id="only-observation",
        run_id=declaration.run_id,
        trial_id=trial.trial_id,
        candidate_id=trial.candidate_id,
        scenario_id=trial.scenario_id,
        source_family_id=trial.source_family_id,
        repetition=1,
        criterion_id="guidance",
        grader_id="manual-fixture",
        grader_version="1",
        value_type="ordinal",
        value="useful",
        status=ObservationStatus.OBSERVED,
    )

    summary = compare_candidates(declaration, [observation], trials=[trial])

    assert summary.decision == ComparisonDecision.INVALID
    assert "no complete paired observations" in summary.decision_reason
    guidance = summary.results[0]
    assert guidance.candidate_b_unavailable == 2


def test_duplicate_observation_invalidates_comparison(smoke_fixture):
    declaration = smoke_fixture.declaration
    case = smoke_fixture.cases[0]
    runner = RecordedResponseRunner(
        declaration=declaration,
        responses={
            (case.candidate_id, case.scenario_id, case.repetition): case.response
        },
    )
    trial = runner.run(
        declaration.candidates[0],
        declaration.scenarios[0],
        repetition=1,
        planned_order=1,
        actual_order=1,
    )
    observation = Observation(
        observation_id="duplicate-one",
        run_id=declaration.run_id,
        trial_id=trial.trial_id,
        candidate_id=trial.candidate_id,
        scenario_id=trial.scenario_id,
        source_family_id=trial.source_family_id,
        repetition=1,
        criterion_id="guidance",
        grader_id="manual-fixture",
        grader_version="1",
        value_type="ordinal",
        value="useful",
        status=ObservationStatus.OBSERVED,
    )
    duplicate = observation.model_copy(update={"observation_id": "duplicate-two"})

    summary = compare_candidates(
        declaration, [observation, duplicate], trials=[trial]
    )

    assert summary.decision == ComparisonDecision.INVALID
    assert "duplicate observations" in summary.decision_reason
