import pytest
from pydantic import ValidationError

from src.evaluation.schemas import (
    EvaluationDeclaration,
    Observation,
    ObservationStatus,
    OfflineFixture,
    ValueType,
)


def test_fixture_round_trip(smoke_fixture):
    restored = OfflineFixture.model_validate_json(smoke_fixture.model_dump_json())

    assert restored == smoke_fixture
    assert restored.declaration.candidates[0].prompt_digest != (
        restored.declaration.candidates[1].prompt_digest
    )


def test_prompt_comparison_rejects_configuration_difference(smoke_fixture):
    data = smoke_fixture.declaration.model_dump(mode="json")
    data["candidates"][1]["configuration"]["model"] = "different-model"

    with pytest.raises(ValidationError, match="identical non-prompt configuration"):
        EvaluationDeclaration.model_validate(data)


def test_fixture_rejects_rating_outside_declared_scale(smoke_fixture):
    data = smoke_fixture.model_dump(mode="json")
    data["cases"][0]["ratings"]["guidance"] = "perfect"

    with pytest.raises(ValidationError, match="outside the guidance scale"):
        OfflineFixture.model_validate(data)


def test_fixture_requires_every_candidate_scenario_repetition(smoke_fixture):
    data = smoke_fixture.model_dump(mode="json")
    data["cases"].pop()

    with pytest.raises(ValidationError, match="missing recorded cases"):
        OfflineFixture.model_validate(data)


def test_non_observed_observation_cannot_have_value():
    with pytest.raises(ValidationError, match="non-observed"):
        Observation(
            observation_id="observation-1",
            run_id="run-1",
            trial_id="trial-1",
            candidate_id="candidate-1",
            scenario_id="scenario-1",
            source_family_id="family-1",
            repetition=1,
            criterion_id="guidance",
            grader_id="grader-1",
            grader_version="1",
            value_type=ValueType.ORDINAL,
            value="useful",
            status=ObservationStatus.ABSTAINED,
        )


def test_schema_rejects_non_ascii_or_path_like_identifiers(smoke_fixture):
    data = smoke_fixture.declaration.model_dump(mode="json")
    data["run_id"] = "../../outside"

    with pytest.raises(ValidationError):
        EvaluationDeclaration.model_validate(data)

    data["run_id"] = "rún"
    with pytest.raises(ValidationError):
        EvaluationDeclaration.model_validate(data)
