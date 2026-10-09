"""Test the fixed-prefix evaluation plumbing without live model calls.

The fake client verifies conversation-history conversion, one-response
generation, combined evaluation, evaluator input boundaries, prompt selection,
configured metrics, and deterministic summaries. It does not test
whether a real evaluator's tutoring-quality judgments are valid.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Generic

import pytest
import yaml
from openai.types.responses import (
    FunctionToolParam,
    ResponseFunctionToolCall,
    ResponseInputParam,
)
from pydantic import BaseModel, TypeAdapter
from typing_extensions import TypedDict

from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.gen_ai import Agent, ToolChoiceTypes
from src.testing.prompt_evaluation.evaluation import (
    build_tutor_history,
    evaluate_next_response,
)
from src.testing.prompt_evaluation.observation import TrialCapture
from src.testing.prompt_evaluation.reporting import print_prompt_summary
from src.testing.prompt_evaluation.types import (
    EvaluationConfig,
    CombinedEvaluationResult,
    EvaluatorRequest,
    ResponseModel,
    TestOutcome,
    TranscriptTurn,
)


TEST_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class FakeTutorResponse:
    output: list[ResponseFunctionToolCall]
    usage: None = None
    output_text: str = ""


@dataclass(frozen=True)
class FakeParsedResponse(Generic[ResponseModel]):
    output_parsed: ResponseModel
    model: str = "test-evaluator-model-version"


@dataclass(frozen=True)
class ParseCall:
    model: str
    instructions: str
    input: str
    text_format: type[BaseModel]
    store: bool


class CreateParams(TypedDict):
    model: str
    instructions: str
    tools: list[FunctionToolParam]
    tool_choice: ToolChoiceTypes
    reasoning: dict[str, str] | None


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses: FakeOpenAIClient = self
        self.create_input: ResponseInputParam | None = None
        self.create_params: CreateParams | None = None
        self.create_calls: int = 0
        self.parse_params: list[ParseCall] = []
        self.ratings: dict[str, TestOutcome] = {
            "factual_correctness": "pass",
            "case_actionability": "fail",
        }

    async def create(
        self,
        *,
        model: str,
        instructions: str,
        input: ResponseInputParam,
        tools: list[FunctionToolParam],
        tool_choice: ToolChoiceTypes,
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
        text_format: type[ResponseModel],
        store: bool,
    ) -> FakeParsedResponse[ResponseModel]:
        self.parse_params.append(
            ParseCall(model, instructions, input, text_format, store)
        )
        evaluator_input = TypeAdapter(EvaluatorRequest).validate_json(input)
        evaluation = text_format.model_validate(
            {
                "results": [
                    {
                        "name": test["name"],
                        "rating": self.ratings[test["name"]],
                        "evidence": ["What output does the assignment require?"],
                        "rationale": (
                            f"Deterministic rationale for {test['name']}."
                        ),
                    }
                    for test in evaluator_input["tests"]
                ]
            }
        )
        return FakeParsedResponse(output_parsed=evaluation)


def test_generates_once_and_runs_each_configured_test(
    capsys: pytest.CaptureFixture[str],
) -> None:
    prefix: list[TranscriptTurn] = [
        {"role": "student", "message": "I need help."},
        {"role": "tutor", "message": "What have you tried?"},
        {"role": "student", "message": "I do not know where to start."},
    ]
    config_data: object = yaml.safe_load(
        (TEST_ROOT / "config.yaml").read_text(encoding="utf-8")
    )
    shared_config = TypeAdapter(EvaluationConfig).validate_python(config_data)
    configured_tests = shared_config["standard_tests"]
    config = shared_config.copy()
    config["evaluator_model"] = "test-evaluator-model"
    config["reference_answer"] = "Identify the required output first."
    config["standard_tests"] = {
        "factual_correctness": configured_tests["factual_correctness"],
    }
    config["case_tests"] = {
        "case_actionability": {
            **configured_tests["usefulness"],
            "evaluator_prompt": "Evaluate actionability only.",
        },
    }
    client = FakeOpenAIClient()
    capture = TrialCapture()

    async def send_message(
        channel_id: int,
        message: str | None = None,
        file: object | None = None,
        view: object | None = None,
    ) -> int:
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
            observer=capture,
        )
    )

    assert result["transcript"][-1] == {
        "role": "tutor",
        "message": "What output does the assignment require?",
    }
    assert result["reference_answer_used"] is True
    assert result["candidate_action"] == "talk_to_user"
    assert result["candidate_model"] == "test-model"
    assert result["openai_evaluator_model"] == "test-evaluator-model-version"
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
    assert set(result["tests"]) == {"factual_correctness", "case_actionability"}
    assert result["tests"]["factual_correctness"]["rating"] == "pass"
    assert result["tests"]["factual_correctness"]["suite"] == "standard"
    assert result["tests"]["case_actionability"]["rating"] == "fail"
    assert result["tests"]["case_actionability"]["suite"] == "case"
    assert result["summary"] == {
        "passed": False,
        "score": 0.5,
        "blocking_tests": ["case_actionability"],
    }
    assert client.create_input == build_tutor_history(prefix)
    assert len(client.parse_params) == 1
    assert capture.generation is not None
    assert capture.generation.request.model == "test-model"
    assert capture.generation.result.response_id is None
    assert capture.selection is None
    assert capture.evaluation is not None
    assert capture.evaluation.result is result

    call = client.parse_params[0]
    evaluator_input = TypeAdapter(EvaluatorRequest).validate_json(call.input)
    assert call.instructions == config.get("evaluator_prompt")
    configured_tests = {
        **config["standard_tests"],
        **config.get("case_tests", {}),
    }
    assert call.model == "test-evaluator-model"
    assert evaluator_input["conversation_prefix"] == prefix
    assert evaluator_input["candidate_response"] == result["transcript"][-1]
    assert evaluator_input["candidate_action"] == "talk_to_user"
    assert evaluator_input.get("reference_answer") == config.get("reference_answer")
    assert {
        test["name"]: test["definition"] for test in evaluator_input["tests"]
    } == {
        name: test["definition"] for name, test in configured_tests.items()
    }
    assert call.text_format is CombinedEvaluationResult

    print_prompt_summary([result])
    assert capsys.readouterr().out == ""
