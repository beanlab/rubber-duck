import asyncio

from scripts.prompt_eval import (
    MetricResult,
    PromptEvaluation,
    TutorReply,
    run,
)


class FakeModel:
    def __init__(self):
        self.student_messages = iter([
            "Why does items[2] cause an error? Please give me a hint.",
            "quit",
        ])
        self.tutor_replies = iter([
            TutorReply(
                action="message",
                message="What index does Python use for the first item?",
                api_items=[{"type": "function_call", "call_id": "call-1"}],
                call_id="call-1",
            ),
            TutorReply(
                action="conclude",
                message=None,
                api_items=[{"type": "function_call", "call_id": "call-2"}],
                call_id="call-2",
            ),
        ])

    async def student(self, model, prompt, transcript):
        return next(self.student_messages)

    async def tutor(self, model, prompt, history):
        return next(self.tutor_replies)

    async def grade(self, model, prompt, transcript, config):
        return PromptEvaluation(
            correctness=MetricResult(passed=True, reason="Technically correct."),
            guidance=MetricResult(passed=True, reason="Provides a targeted hint."),
            disclosure=MetricResult(passed=True, reason="Does not reveal the fix."),
        )


def test_evaluates_one_prompt_on_three_metrics(tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Tutor prompt", encoding="utf-8")
    config = {
        "model": "test-model",
        "prompt_path": str(prompt),
        "max_tutor_turns": 2,
        "student_prompt": "Student prompt",
        "reference_answer": "Lists start at index zero.",
        "allowed_help": "Hints only.",
        "metrics": {
            "correctness": "Correct technical content.",
            "guidance": "Useful hint.",
            "disclosure": "No final solution.",
        },
        "evaluator_prompt": "Evaluate the transcript.",
    }

    result = asyncio.run(run(config, FakeModel()))

    assert result["prompt_passed"] is True
    assert set(result["metrics"]) == {"correctness", "guidance", "disclosure"}
    assert [turn["role"] for turn in result["transcript"]] == [
        "student",
        "tutor",
        "student",
        "tutor",
    ]
