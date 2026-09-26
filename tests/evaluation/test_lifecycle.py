import pytest

from src.evaluation.lifecycle import (
    InvalidTransitionError,
    transition_run,
    transition_trial,
)
from src.evaluation.schemas import RunLifecycle, TrialLifecycle


def test_run_follows_declared_lifecycle():
    state = RunLifecycle.DRAFT
    for target in (
        RunLifecycle.VALIDATED,
        RunLifecycle.PREPARED,
        RunLifecycle.RUNNING,
        RunLifecycle.EXECUTED,
        RunLifecycle.GRADING,
        RunLifecycle.GRADED,
        RunLifecycle.ANALYZED,
        RunLifecycle.REPORTED,
    ):
        state = transition_run(state, target)

    assert state == RunLifecycle.REPORTED


def test_invalid_run_transition_fails_loudly():
    with pytest.raises(InvalidTransitionError):
        transition_run(RunLifecycle.DRAFT, RunLifecycle.REPORTED)


def test_active_run_can_fail_but_terminal_run_cannot_restart():
    assert transition_run(RunLifecycle.RUNNING, RunLifecycle.FAILED) == RunLifecycle.FAILED
    with pytest.raises(InvalidTransitionError):
        transition_run(RunLifecycle.FAILED, RunLifecycle.RUNNING)


def test_trial_requires_running_before_terminal_state():
    with pytest.raises(InvalidTransitionError):
        transition_trial(TrialLifecycle.PENDING, TrialLifecycle.SUCCEEDED)
    assert (
        transition_trial(TrialLifecycle.RUNNING, TrialLifecycle.SUCCEEDED)
        == TrialLifecycle.SUCCEEDED
    )
