import asyncio
import copy

import pytest

from scripts.prompt_eval import (
    Grade,
    StandardResult,
    TutorAction,
    evaluate,
    match_results_to_standards,
    summarize,
)


class FakeModel:
    def __init__(self):
        self.student_messages = iter([
            "What is a Python variable?",
            "quit",
        ])
        self.tutor_actions = iter([
            TutorAction(
                kind="message",
                message="A variable is a name associated with a value.",
                response_items=[
                    {
                        "type": "function_call",
                        "name": "talk_to_user",
                        "call_id": "call-1",
                        "arguments": '{"message_to_user":"A variable is a name associated with a value."}',
                    }
                ],
                call_id="call-1",
            ),
            TutorAction(
                kind="conclude",
                message=None,
                response_items=[
                    {
                        "type": "function_call",
                        "name": "conclude_conversation",
                        "call_id": "call-2",
                        "arguments": "{}",
                    }
                ],
                call_id="call-2",
            ),
        ])
        self.tutor_calls = []

    async def text(self, *, model, instructions, input_text):
        return next(self.student_messages)

    async def tutor(self, *, model, instructions, input_items):
        self.tutor_calls.append(
            {"instructions": instructions, "input_items": copy.deepcopy(input_items)}
        )
        return next(self.tutor_actions)

    async def grade(self, *, model, instructions, input_text):
        return Grade(
            results=[
                StandardResult(
                    standard_id="defines-variable",
                    passed=True,
                    evidence_turns=[2],
                    evidence_quote="variable is a name associated with a value",
                    reason="The tutor gives the required definition.",
                ),
                StandardResult(
                    standard_id="concludes-after-quit",
                    passed=True,
                    evidence_turns=[3, 4],
                    evidence_quote="quit",
                    reason="The student quits before the tutor concludes.",
                ),
            ]
        )


def config():
    return {
        "models": {"student": "s", "tutor": "t", "evaluator": "e"},
        "student_prompt": "student simulator",
        "evaluator_prompt": "conversation evaluator",
        "metrics": {
            "correctness": {},
            "conversation_control": {},
        },
        "scenarios": [
            {
                "id": "variables",
                "learner": "beginner",
                "task": "learn variables",
                "reference": "A variable associates a name with a value.",
                "permitted_help": "Explain fully.",
                "completion_message": "quit",
                "max_tutor_turns": 2,
                "student_script": ["Ask about variables.", "Send quit."],
                "conversation_standard": [
                    {
                        "standard_id": "defines-variable",
                        "metric": "correctness",
                        "pass_when": "The tutor defines a variable.",
                    },
                    {
                        "standard_id": "concludes-after-quit",
                        "metric": "conversation_control",
                        "pass_when": "The tutor concludes only after quit.",
                    },
                ],
            }
        ],
    }


def test_complete_conversation_uses_tutor_tools_and_grades_transcript():
    fake = FakeModel()

    result = asyncio.run(evaluate(config(), "production prompt", fake))

    conversation = result["conversations"][0]
    assert [turn["role"] for turn in conversation["transcript"]] == [
        "student",
        "tutor",
        "student",
        "tutor",
    ]
    assert conversation["transcript"][-1]["action"] == "conclude_conversation"
    assert conversation["stop_reason"] == "tutor_concluded"
    assert fake.tutor_calls[0]["instructions"] == "production prompt"
    assert fake.tutor_calls[1]["input_items"][-1] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "quit",
    }
    assert result["prompt_passed"] is True


def test_evaluator_quote_must_exist_in_its_cited_turns():
    grade = Grade(
        results=[
            StandardResult(
                standard_id="required",
                passed=True,
                evidence_turns=[1],
                evidence_quote="not actually present",
                reason="Unsupported.",
            )
        ]
    )
    standards = [
        {
            "standard_id": "required",
            "metric": "guidance",
            "pass_when": "Do the thing.",
        }
    ]
    transcript = [
        {"turn": 1, "role": "tutor", "action": "message", "content": "Hello"}
    ]

    with pytest.raises(ValueError, match="quote is absent"):
        match_results_to_standards(grade, standards, transcript)


def test_summary_requires_every_conversation_standard_to_pass():
    conversations = [
        {
            "standard_results": [
                {"metric": "correctness", "passed": True},
                {"metric": "guidance", "passed": True},
            ]
        },
        {
            "standard_results": [
                {"metric": "correctness", "passed": False},
                {"metric": "guidance", "passed": True},
            ]
        },
    ]

    result = summarize(
        conversations,
        {"correctness": {}, "guidance": {}},
    )

    assert result["metrics"]["correctness"]["pass_rate"] == 0.5
    assert result["metrics"]["guidance"]["pass_rate"] == 1.0
    assert result["prompt_passed"] is False
