import pytest

from evaluation.grading import build_grader_input, evaluate_criteria

pytestmark = pytest.mark.skip(reason="Function signatures only; implementation pending.")


# Keep candidate-controlled content separate from trusted criteria and reference facts.
@pytest.mark.parametrize(("evidence", "criteria", "reference_answer"), [])
def test_grader_input(evidence, criteria, reference_answer):
    ...


# Accept complete judgments and reject missing, duplicate, unknown, or malformed criteria results.
@pytest.mark.parametrize(("criteria", "judge_response", "expected_error"), [])
def test_grader_judgments(criteria, judge_response, expected_error, monkeypatch):
    ...


# Record judge usage and failures separately without converting grading errors into quality scores.
@pytest.mark.parametrize(("judge_outcome", "expected_events", "expected_status"), [])
def test_grader_outcomes(judge_outcome, expected_events, expected_status, monkeypatch):
    ...
