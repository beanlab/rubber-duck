"""Test the fixed-prefix evaluation plumbing without live model calls.

The fake client verifies conversation-history conversion, one-response
generation, independent test calls, evaluator input boundaries, prompt
selection, configured metrics, and deterministic summaries. It does not test
whether a real evaluator's tutoring-quality judgments are valid.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from openai.types.responses import (
    FunctionToolParam,
    ResponseFunctionToolCall,
    ResponseInputParam,
)

from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.gen_ai import Agent
from src.testing.prompt_evaluation.evaluation import (
    build_tutor_history,
    evaluate_next_response,
)
from src.testing.prompt_evaluation.types import (
    EvaluationConfig,
    EvaluationResult,
    EvaluatorRequest,
    TranscriptTurn,
)


TEST_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class FakeTutorResponse:
    output: list[ResponseFunctionToolCall]
    usage: None = None
    output_text: str = ""


@dataclass(frozen=True)
class FakeParsedResponse:
    output_parsed: EvaluationResult


@dataclass(frozen=True)
class ParseCall:
    model: str
    instructions: str
    input: str
    text_format: type[EvaluationResult]
    store: bool


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses: FakeOpenAIClient = self
        self.create_input: ResponseInputParam | None = None
        self.create_params: dict[str, Any] = {}
        self.create_calls: int = 0
        self.parse_params: list[ParseCall] = []
        self.ratings: dict[str, str] = {
            "subject_accuracy": "pass",
            "actionability": "fail",
        }

    async def create(
        self,
        *,
        model: str,
        instructions: str,
        input: ResponseInputParam,
        tools: list[FunctionToolParam],
        tool_choice: Any,
        reasoning: dict[str, str] | None = None,
    ) -> FakeTutorResponse:
        self.create_calls += 1
        self.create_input = input
        self.create_params = {
            "model": model,
            "instructions": instructions,
            "tools": tools,
            "tool_choice": tool_choice,
            "reasoning": reasoning,
        }
        call = ResponseFunctionToolCall(
            type="function_call",
            name="talk_to_user",
            call_id="fake_call",
            arguments=json.dumps(
                {"message_to_user": "What output does the assignment require?"}
            ),
        )
        return FakeTutorResponse(output=[call])

    async def parse(
        self,
        *,
        model: str,
        instructions: str,
        input: str,
        text_format: type[EvaluationResult],
        store: bool,
    ) -> FakeParsedResponse:
        self.parse_params.append(
            ParseCall(model, instructions, input, text_format, store)
        )
        evaluator_input = cast(EvaluatorRequest, json.loads(input))
        test_name = evaluator_input["test"]["name"]
        evaluation = text_format(
            rating=self.ratings[test_name],
            evidence=["What output does the assignment require?"],
            rationale=f"Deterministic rationale for {test_name}.",
        )
        return FakeParsedResponse(output_parsed=evaluation)


def test_generates_once_and_runs_each_configured_test() -> None:
    prefix: list[TranscriptTurn] = [
        {"role": "student", "message": "I need help."},
        {"role": "tutor", "message": "What have you tried?"},
        {"role": "student", "message": "I do not know where to start."},
    ]
    shared_config = cast(
        EvaluationConfig,
        yaml.safe_load((TEST_ROOT / "config.yaml").read_text(encoding="utf-8")),
    )
    configured_tests = shared_config["tests"]
    config: EvaluationConfig = {
        **shared_config,
        "evaluator_model": "test-evaluator-model",
        "reference_answer": "Identify the required output first.",
        "tests": {
            "subject_accuracy": configured_tests["subject_accuracy"],
            "actionability": {
                **configured_tests["actionability"],
                "evaluator_prompt": "Evaluate actionability only.",
            },
        },
    }
    client = FakeOpenAIClient()

    async def send_message(*_args: Any, **_kwargs: Any) -> int:
        return 1

    armory = Armory(send_message)
    armory.scrub_tools(TalkTool(send_message))
    agent = Agent(
        name="RubberDuck",
        prompt="Tutor prompt",
        model="test-model",
        tools=["talk_to_user", "conclude_conversation"],
        reasoning="low",
    )

    result = asyncio.run(
        evaluate_next_response(
            client=client,
            config=config,
            transcript=prefix,
            agent=agent,
            armory=armory,
        )
    )

    assert result["transcript"][-1] == {
        "role": "tutor",
        "message": "What output does the assignment require?",
    }
    assert result["reference_answer_used"] is True
    assert client.create_calls == 1
    assert client.create_params == {
        "model": "test-model",
        "instructions": "Tutor prompt",
        "tools": [
            armory.get_tool_schema("talk_to_user"),
            armory.get_tool_schema("conclude_conversation"),
        ],
        "tool_choice": "auto",
        "reasoning": {"effort": "low"},
    }
    assert set(result["tests"]) == set(config["tests"])
    assert result["tests"]["subject_accuracy"]["rating"] == "pass"
    assert result["tests"]["actionability"]["rating"] == "fail"
    assert result["summary"] == {
        "passed": False,
        "score": 0.5,
        "blocking_tests": ["actionability"],
    }
    assert client.create_input == build_tutor_history(prefix)
    assert len(client.parse_params) == 2

    evaluator_calls: dict[str, ParseCall] = {}
    for call in client.parse_params:
        evaluator_input = cast(EvaluatorRequest, json.loads(call.input))
        evaluator_calls[evaluator_input["test"]["name"]] = call

    assert evaluator_calls["subject_accuracy"].instructions == config.get(
        "evaluator_prompt"
    )
    assert (
        evaluator_calls["actionability"].instructions
        == config["tests"]["actionability"].get("evaluator_prompt")
    )
    for test_name, call in evaluator_calls.items():
        evaluator_input = cast(EvaluatorRequest, json.loads(call.input))
        assert call.model == "test-evaluator-model"
        assert evaluator_input["conversation_prefix"] == prefix
        assert evaluator_input["candidate_response"] == result["transcript"][-1]
        assert evaluator_input.get("reference_answer") == config.get(
            "reference_answer"
        )
        assert evaluator_input["test"]["definition"] == config["tests"][test_name][
            "definition"
        ]
        assert call.text_format is EvaluationResult
