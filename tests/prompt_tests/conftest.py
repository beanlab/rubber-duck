"""Pytest reporting support for live prompt evaluations."""

import pytest

from experiments.evaluation.console import print_prompt_summary
from experiments.evaluation.types import EvaluationCase, EvaluationRun


PROMPT_CASE_RESULTS: list[tuple[EvaluationCase, EvaluationRun]] = []


@pytest.fixture(scope="session")
def prompt_case_results() -> list[tuple[EvaluationCase, EvaluationRun]]:
    """Collect completed live evaluations for the terminal summary."""
    PROMPT_CASE_RESULTS.clear()
    return PROMPT_CASE_RESULTS


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary() -> None:
    """Print the aggregate prompt report after pytest's failure sections."""
    if not PROMPT_CASE_RESULTS:
        return
    print_prompt_summary(
        [result for _, result in PROMPT_CASE_RESULTS],
        cases=[case for case, _ in PROMPT_CASE_RESULTS],
    )
