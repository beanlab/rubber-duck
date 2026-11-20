import pytest

from harness.experiment import (
    create_plan,
    load_inputs,
    run_experiment,
    run_pytest,
    validate_collection,
)

pytestmark = pytest.mark.skip(reason="Function signatures only; implementation pending.")


# Preserve standalone defaults and reject invalid experiment input manifests.
@pytest.mark.parametrize(("manifest", "expected_inputs", "expected_error"), [])
def test_run_inputs(manifest, expected_inputs, expected_error, tmp_path):
    ...


# Freeze candidate inputs and the case population before any candidate executes.
@pytest.mark.parametrize(("test_ids", "candidates", "repetitions", "expected_error"), [])
def test_experiment_plan(test_ids, candidates, repetitions, expected_error):
    ...


# Reject mismatched collected cases and pytest settings that silently change planned attempts.
@pytest.mark.parametrize(("collected_ids", "pytest_options", "expected_error"), [])
def test_collection_and_attempt_policy(collected_ids, pytest_options, expected_error):
    ...


# Give every planned candidate repetition its own inputs, output destination, and recorded outcome.
@pytest.mark.parametrize(("plan", "process_outcomes", "expected_attempts"), [])
def test_experiment_execution(plan, process_outcomes, expected_attempts, tmp_path, monkeypatch):
    ...
