import asyncio

from scripts.prompt_eval import (
    CriterionResult,
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
            subject_accuracy=CriterionResult(
                rating="correct",
                evidence=["What index does Python use for the first item?"],
                rationale="The tutor makes no incorrect technical claim.",
            ),
            misconception_diagnosis=CriterionResult(
                rating="accurately_recognizes",
                evidence=["What index does Python use for the first item?"],
                rationale="The question targets the student's indexing misconception.",
            ),
            guidance_scaffolding=CriterionResult(
                rating="useful",
                evidence=["What index does Python use for the first item?"],
                rationale="The tutor provides a targeted next step.",
            ),
            answer_disclosure=CriterionResult(
                rating="appropriate",
                evidence=["What index does Python use for the first item?"],
                rationale="The tutor does not reveal the completed fix.",
            ),
            relevance=CriterionResult(
                rating="relevant",
                evidence=["What index does Python use for the first item?"],
                rationale="The response addresses list indexing.",
            ),
            actionability=CriterionResult(
                rating="actionable",
                evidence=["What index does Python use for the first item?"],
                rationale="The student can identify the first valid index next.",
            ),
            learner_self_correction=CriterionResult(
                rating="not_demonstrated",
                evidence=["quit"],
                rationale="The student quits without stating the corrected indexes.",
            ),
        )


def test_evaluates_one_prompt_on_anchored_criteria(tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Tutor prompt", encoding="utf-8")
    config = {
        "model": "test-model",
        "prompt_path": str(prompt),
        "max_tutor_turns": 2,
        "student_prompt": "Student prompt",
        "reference_answer": "Lists start at index zero.",
        "allowed_help": "Hints only.",
        "criteria": {
            "subject_accuracy": {},
            "misconception_diagnosis": {},
            "guidance_scaffolding": {},
            "answer_disclosure": {},
            "relevance": {},
            "actionability": {},
            "learner_self_correction": {},
        },
        "evaluator_prompt": "Evaluate the transcript.",
    }

    result = asyncio.run(run(config, FakeModel()))

    assert set(result["criteria"]) == {
        "subject_accuracy",
        "misconception_diagnosis",
        "guidance_scaffolding",
        "answer_disclosure",
        "relevance",
        "actionability",
        "learner_self_correction",
    }
    assert result["criteria"]["guidance_scaffolding"]["rating"] == "useful"
    assert result["summary"] == {
        "guardrails": "PASSED",
        "tutoring_quality": "STRONG",
        "learner_self_correction": {
            "rating": "not_demonstrated",
            "evidence": ["quit"],
            "rationale": "The student quits without stating the corrected indexes.",
        },
        "result": "STRONG TUTOR RESPONSE WITH INCOMPLETE OUTCOME EVIDENCE",
    }
    assert [turn["role"] for turn in result["transcript"]] == [
        "student",
        "tutor",
        "student",
        "tutor",
    ]
