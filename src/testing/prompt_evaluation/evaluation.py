"""Generate and evaluate one tutor response after a fixed conversation prefix."""

import asyncio
import json

from openai.types.responses import (
    EasyInputMessageParam,
    ResponseFunctionToolCallParam,
    ResponseInputParam,
)
from openai.types.responses.response_input_param import FunctionCallOutput
from pydantic import BaseModel

from src.armory.armory import Armory
from src.gen_ai.completion import CompletionRequest, ResponsesCompletionAdapter
from src.gen_ai.gen_ai import Agent
from src.testing.prompt_evaluation.types import (
    EvaluationClient,
    EvaluationConfig,
    EvaluationResult,
    EvaluationRun,
    EvaluationSummary,
    EvaluationTestConfig,
    EvaluatorContext,
    EvaluatorRequest,
    TestOutcome,
    TestResult,
    TranscriptTurn,
)


TEST_OUTCOMES: frozenset[TestOutcome] = frozenset(
    {"pass", "fail", "inconclusive"}
)


class TutorMessageArguments(BaseModel):
    message_to_user: str


def build_tutor_history(transcript: list[TranscriptTurn]) -> ResponseInputParam:
    """Convert student/tutor turns into the tool history used by the tutor."""
    history: ResponseInputParam = []
    pending_call_id: str | None = None

    for index, turn in enumerate(transcript, start=1):
        role = turn["role"]
        message = turn["message"]
        if role == "student":
            if pending_call_id is None:
                user_message: EasyInputMessageParam = {
                    "role": "user",
                    "content": message,
                }
                history.append(user_message)
            else:
                tool_output: FunctionCallOutput = {
                    "type": "function_call_output",
                    "call_id": pending_call_id,
                    "output": message,
                }
                history.append(tool_output)
                pending_call_id = None
            continue

        if pending_call_id is not None:
            raise ValueError("Tutor turns must be followed by a student turn")

        pending_call_id = f"prefix_call_{index}"
        tool_call: ResponseFunctionToolCallParam = {
            "type": "function_call",
            "call_id": pending_call_id,
            "name": "talk_to_user",
            "arguments": json.dumps({"message_to_user": message}),
        }
        history.append(tool_call)

    if pending_call_id is not None:
        raise ValueError("A prefix must end with a student message")
    return history


def _evaluation_tests(
    config: EvaluationConfig,
) -> dict[str, EvaluationTestConfig]:
    tests = config.get("tests", {})
    if not tests:
        raise ValueError("Evaluation config must define at least one test")
    for name, test in tests.items():
        if not test.get("definition") or not test.get("metric"):
            raise ValueError(f"Evaluation test {name!r} needs a definition and metric")
        if not test.get("evaluator_prompt") and not config.get("evaluator_prompt"):
            raise ValueError(f"Evaluation test {name!r} needs an evaluator prompt")
        for rating, level in test["metric"].items():
            if not level.get("definition"):
                raise ValueError(f"Metric rating {name}.{rating} needs a definition")
            if level.get("outcome") not in TEST_OUTCOMES | {None}:
                raise ValueError(
                    f"Metric rating {name}.{rating} has an invalid outcome"
                )
            score = level.get("score")
            if score is not None and not 0 <= score <= 1:
                raise ValueError(f"Metric rating {name}.{rating} has an invalid score")
    return tests


def _response_message(outputs: list[dict]) -> str:
    calls = [
        item
        for item in outputs
        if item.get("type") == "function_call"
    ]
    if len(calls) > 1:
        raise RuntimeError("Tutor returned more than one action")

    if calls:
        call = calls[0]
        if call["name"] == "conclude_conversation":
            return "[conversation concluded]"
        if call["name"] != "talk_to_user":
            raise RuntimeError(f"Unsupported tutor tool: {call['name']}")
        message = TutorMessageArguments.model_validate_json(
            call["arguments"]
        ).message_to_user.strip()
    else:
        message = next(
            (
                content["text"].strip()
                for item in outputs
                if item.get("type") == "message"
                for content in item.get("content", [])
                if content.get("type") == "output_text"
            ),
            "",
        )

    if not message:
        raise RuntimeError("Tutor returned an empty message")
    return message


async def _evaluate_test(
    *,
    client: EvaluationClient,
    config: EvaluationConfig,
    test_name: str,
    test: EvaluationTestConfig,
    evaluator_input: EvaluatorContext,
) -> TestResult:
    """Run one configured test against a generated tutor response."""
    test_input: EvaluatorRequest = {
        **evaluator_input,
        "test": {
            "name": test_name,
            "definition": test["definition"],
            "metric": {
                rating: level["definition"]
                for rating, level in test["metric"].items()
            },
        },
    }
    evaluator_prompt = test.get("evaluator_prompt") or config.get(
        "evaluator_prompt"
    )
    if evaluator_prompt is None:
        raise ValueError(f"Evaluation test {test_name!r} needs an evaluator prompt")
    response = await client.responses.parse(
        model=config["evaluator_model"],
        instructions=evaluator_prompt,
        input=json.dumps(test_input, indent=2),
        text_format=EvaluationResult,
        store=False,
    )
    if response.output_parsed is None:
        raise RuntimeError(f"Evaluator returned no result for test: {test_name}")

    judgment = response.output_parsed
    rating = judgment.rating
    if rating not in test["metric"]:
        raise RuntimeError(
            f"Evaluator returned unknown rating {rating!r} for {test_name}"
        )
    level = test["metric"][rating]
    return {
        "rating": rating,
        "evidence": judgment.evidence,
        "rationale": judgment.rationale,
        "score": level.get("score"),
        "outcome": level.get("outcome"),
    }


def summarize_evaluation(tests: dict[str, TestResult]) -> EvaluationSummary:
    """Calculate deterministic case-level outcomes from configured metrics."""
    blocking_tests = [
        name
        for name, result in tests.items()
        if result["outcome"] in {"fail", "inconclusive"}
    ]
    scores = [
        result["score"]
        for result in tests.values()
        if result["score"] is not None
    ]
    return {
        "passed": not blocking_tests,
        "score": sum(scores) / len(scores) if scores else None,
        "blocking_tests": blocking_tests,
    }


async def evaluate_next_response(
    *,
    client: EvaluationClient,
    config: EvaluationConfig,
    transcript: list[TranscriptTurn],
    agent: Agent,
    armory: Armory,
    completion_adapter: ResponsesCompletionAdapter | None = None,
) -> EvaluationRun:
    """Generate one response, then run every configured test against it."""
    configured_tests = _evaluation_tests(config)
    adapter = completion_adapter or ResponsesCompletionAdapter()
    completion = await adapter.complete(
        client,
        CompletionRequest(
            model=agent.model,
            instructions=agent.prompt,
            input=build_tutor_history(transcript),
            tools=[armory.get_tool_schema(name) for name in agent.tools],
            tool_choice=agent.tool_settings,
            output_format=agent.output_format,
            reasoning=agent.reasoning,
        ),
    )
    candidate_response: TranscriptTurn = {
        "role": "tutor",
        "message": _response_message(completion.output),
    }
    evaluator_input: EvaluatorContext = {
        "conversation_prefix": transcript,
        "candidate_response": candidate_response,
        "tutor_prompt": agent.prompt,
    }
    reference_answer = config.get("reference_answer")
    if config.get("use_reference_answer", True) and reference_answer:
        evaluator_input["reference_answer"] = reference_answer

    test_results = await asyncio.gather(
        *(
            _evaluate_test(
                client=client,
                config=config,
                test_name=test_name,
                test=test,
                evaluator_input=evaluator_input,
            )
            for test_name, test in configured_tests.items()
        )
    )
    tests: dict[str, TestResult] = dict(zip(configured_tests, test_results))

    return {
        "transcript": [*transcript, candidate_response],
        "tests": tests,
        "summary": summarize_evaluation(tests),
        "reference_answer_used": "reference_answer" in evaluator_input,
    }
