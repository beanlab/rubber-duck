import asyncio

from scripts.prompt_eval import (
    Grade,
    StandardResult,
    evaluate,
    match_results_to_standards,
    summarize,
)


class FakeModel:
    def __init__(self):
        self.text_outputs = iter([
            "What is a variable?",
            "A variable is a name for a value.",
            "Can you give me a hint?",
            "Look at the valid index range.",
        ])
        self.grades = iter([
            Grade(
                results=[
                    StandardResult(standard_id="one-correct", passed=True, evidence="name for a value", reason="Correct."),
                    StandardResult(standard_id="one-guide", passed=True, evidence="example", reason="Useful."),
                    StandardResult(standard_id="one-disclose", passed=True, evidence="none", reason="Appropriate."),
                ]
            ),
            Grade(
                results=[
                    StandardResult(standard_id="two-correct", passed=False, evidence="none", reason="Missing the key fact."),
                    StandardResult(standard_id="two-guide", passed=True, evidence="valid index range", reason="Actionable."),
                    StandardResult(standard_id="two-disclose", passed=True, evidence="none", reason="No solution given."),
                ]
            ),
        ])
        self.instructions = []

    async def text(self, *, model, instructions, input_text):
        self.instructions.append(instructions)
        return next(self.text_outputs)

    async def grade(self, *, model, instructions, input_text):
        self.instructions.append(instructions)
        return next(self.grades)


def test_three_agent_flow_uses_candidate_prompt_for_answerer():
    config = {
        "models": {"questioner": "q", "answerer": "a", "evaluator": "e"},
        "candidate_prompt": "candidate",
        "questioner_prompt": "questioner",
        "evaluator_prompt": "evaluator",
        "metrics": {name: {} for name in ("correctness", "guidance", "disclosure")},
        "scenarios": [
            {
                "id": "one", "learner": "beginner", "task": "ask", "reference": "x", "permitted_help": "explain",
                "response_standard": [
                    {"standard_id": "one-correct", "metric": "correctness", "pass_when": "correct"},
                    {"standard_id": "one-guide", "metric": "guidance", "pass_when": "useful"},
                    {"standard_id": "one-disclose", "metric": "disclosure", "pass_when": "within boundary"},
                ],
            },
            {
                "id": "two", "learner": "beginner", "task": "ask", "reference": "y", "permitted_help": "hint",
                "response_standard": [
                    {"standard_id": "two-correct", "metric": "correctness", "pass_when": "correct"},
                    {"standard_id": "two-guide", "metric": "guidance", "pass_when": "useful"},
                    {"standard_id": "two-disclose", "metric": "disclosure", "pass_when": "within boundary"},
                ],
            },
        ],
    }
    fake = FakeModel()

    result = asyncio.run(evaluate(config, "candidate", fake))

    assert fake.instructions == [
        "questioner", "candidate", "evaluator",
        "questioner", "candidate", "evaluator",
    ]
    assert result["metrics"]["correctness"]["pass_rate"] == 0.5
    assert result["metrics"]["guidance"]["pass_rate"] == 1.0
    assert result["prompt_passed"] is False


def test_evaluator_must_grade_every_declared_standard():
    grade = Grade(
        results=[
            StandardResult(standard_id="required", passed=True, evidence="quote", reason="Present."),
        ]
    )
    standards = [
        {"standard_id": "required", "metric": "guidance", "pass_when": "Do the thing"},
    ]

    assert match_results_to_standards(grade, standards)[0]["passed"] is True


def test_summary_passes_only_when_every_metric_clears_its_threshold():
    trials = [
        {"standard_results": [
            {"metric": "correctness", "passed": True},
            {"metric": "guidance", "passed": True},
            {"metric": "disclosure", "passed": True},
        ]},
        {"standard_results": [
            {"metric": "correctness", "passed": True},
            {"metric": "guidance", "passed": True},
            {"metric": "disclosure", "passed": True},
        ]},
    ]
    metrics = {name: {} for name in ("correctness", "guidance", "disclosure")}

    result = summarize(trials, metrics)

    assert result["prompt_passed"] is True
