"""Validated lifecycle transitions for runs and trials."""

from .schemas import RunLifecycle, TrialLifecycle


class InvalidTransitionError(ValueError):
    pass


RUN_TRANSITIONS: dict[RunLifecycle, frozenset[RunLifecycle]] = {
    RunLifecycle.DRAFT: frozenset({RunLifecycle.VALIDATED}),
    RunLifecycle.VALIDATED: frozenset({RunLifecycle.PREPARED}),
    RunLifecycle.PREPARED: frozenset({RunLifecycle.RUNNING}),
    RunLifecycle.RUNNING: frozenset({RunLifecycle.EXECUTED}),
    RunLifecycle.EXECUTED: frozenset({RunLifecycle.GRADING}),
    RunLifecycle.GRADING: frozenset({RunLifecycle.GRADED}),
    RunLifecycle.GRADED: frozenset({RunLifecycle.ANALYZED}),
    RunLifecycle.ANALYZED: frozenset({RunLifecycle.REPORTED}),
    RunLifecycle.REPORTED: frozenset(),
    RunLifecycle.FAILED: frozenset(),
    RunLifecycle.CANCELLED: frozenset(),
}

TRIAL_TRANSITIONS: dict[TrialLifecycle, frozenset[TrialLifecycle]] = {
    TrialLifecycle.PENDING: frozenset({TrialLifecycle.RUNNING}),
    TrialLifecycle.RUNNING: frozenset(
        {
            TrialLifecycle.SUCCEEDED,
            TrialLifecycle.FAILED,
            TrialLifecycle.INVALID,
        }
    ),
    TrialLifecycle.SUCCEEDED: frozenset(),
    TrialLifecycle.FAILED: frozenset(),
    TrialLifecycle.INVALID: frozenset(),
}


def transition_run(current: RunLifecycle, target: RunLifecycle) -> RunLifecycle:
    if target in {RunLifecycle.FAILED, RunLifecycle.CANCELLED} and current not in {
        RunLifecycle.REPORTED,
        RunLifecycle.FAILED,
        RunLifecycle.CANCELLED,
    }:
        return target
    if target not in RUN_TRANSITIONS[current]:
        raise InvalidTransitionError(f"invalid run transition: {current} -> {target}")
    return target


def transition_trial(
    current: TrialLifecycle, target: TrialLifecycle
) -> TrialLifecycle:
    if target not in TRIAL_TRANSITIONS[current]:
        raise InvalidTransitionError(f"invalid trial transition: {current} -> {target}")
    return target
