"""Reusable provider fakes for deterministic prompt-evaluation tests."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic

from openai.types.responses import (
    FunctionToolParam,
    ResponseFunctionToolCall,
    ResponseInputParam,
)
from pydantic import BaseModel, TypeAdapter
from typesafe_sdk import JSONContent, Question, SystemOneResponse
from typing_extensions import TypedDict

from experiments.evaluation.types import (
    EvaluatorRequest,
    ResponseModel,
    TestOutcome,
)
from src.gen_ai.gen_ai import ToolChoiceTypes


@dataclass(frozen=True)
class FakeTutorResponse:
    output: list[ResponseFunctionToolCall]
    usage: None = None
    output_text: str = ""
    id: str = "test-response-id"
    model: str = "test-model-version"


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
            "concise_response": "pass",
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


class FakeJevClient:
    def __init__(self) -> None:
        self.states: list[JSONContent] = []
        self.questions: list[dict[str, Question]] = []
        self.models: list[str | None] = []

    async def system_one(
        self,
        state: JSONContent,
        questions: Mapping[str, Question],
        *,
        model: str | None = None,
    ) -> SystemOneResponse:
        self.states.append(state)
        self.questions.append(dict(questions))
        self.models.append(model)
        answers: dict[str, object] = {}
        for name in questions:
            if name.startswith("applies::"):
                applicable = name == "applies::solution_boundary"
                answers[name] = {
                    "type": "choice",
                    "choice": "applicable" if applicable else "not_applicable",
                    "confidence": 0.8,
                    "probabilities": {
                        "applicable": 0.9 if applicable else 0.05,
                        "not_applicable": 0.05 if applicable else 0.9,
                        "insufficient_evidence": 0.05,
                    },
                }
            else:
                rating = "fail" if name == "grade::guidance" else "pass"
                answers[name] = {
                    "type": "choice",
                    "choice": rating,
                    "confidence": 0.8,
                    "probabilities": {
                        "pass": 0.9 if rating == "pass" else 0.2,
                        "fail": 0.1 if rating == "pass" else 0.8,
                    },
                }
        return SystemOneResponse.model_validate(
            {"model": "jev-test", "usage": {}, "answers": answers}
        )
