import pytest

pytestmark = pytest.mark.skip(reason="Function signatures only; implementation pending.")


# Exercise real collection and fixtures with standalone defaults and experiment-supplied prompts.
@pytest.mark.parametrize(("run_inputs", "expected_cases", "expected_requests"), [])
def test_evaluation_inputs(pytester, run_inputs, expected_cases, expected_requests):
    ...


# Reject changed collection before any application fixture or live dependency starts.
def test_collection_rejection_precedes_execution(pytester):
    ...


# Preserve actual pytest setup, assertion, and teardown failures in saved trial evidence.
@pytest.mark.parametrize(("failure_phase", "expected_status"), [])
def test_pytest_phase_recording(pytester, failure_phase, expected_status):
    ...


# Terminate a hung child process and retain its partial evidence and planned attempt identity.
def test_subprocess_timeout(pytester, tmp_path):
    ...


