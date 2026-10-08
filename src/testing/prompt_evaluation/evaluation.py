"""Generate and evaluate one tutor response after a fixed conversation prefix."""

import json
from collections.abc import Sequence
from dataclasses import dataclass

from openai.types.responses import (
    EasyInputMessageParam,
    ResponseFunctionToolCallParam,
    ResponseInputParam,
)
from openai.types.responses.response_input_param import FunctionCallOutput
from pydantic import BaseModel, Field

from src.armory.armory import Armory
from src.gen_ai.completion import CompletionRequest, ResponsesCompletionAdapter
from src.gen_ai.gen_ai import Agent
from src.testing.prompt_evaluation.jev import JevEvaluator
from src.testing.prompt_evaluation.types import (
    EvaluationClient,
    CombinedEvaluationResult,
    EvaluationConfig,
    EvaluationRun,
    EvaluationSummary,
    EvaluationTestConfig,
    EvaluatorContext,
    EvaluatorRequest,
    JevEvaluation,
    ResponseAction,
    RubberDuckTestConfig,
    TestOutcome,
    TestResult,
    TestSelection,
    TestSuite,
    TranscriptTurn,
)


class TutorMessageArguments(BaseModel):
    message_to_user: str


class CompletionContent(BaseModel):
    type: str
    text: str | None = None


class CompletionOutputItem(BaseModel):
    type: str
    name: str | None = None
    arguments: str | None = None
    content: list[CompletionContent] = Field(default_factory=list)


@dataclass(frozen=True)
class PreparedEvaluation:
    """Generated candidate and JEV-selected tests awaiting OpenAI grading."""

    transcript: list[TranscriptTurn]
    candidate_action: ResponseAction
    candidate_model: str
    evaluator_model: str
    evaluator_prompt: str
    evaluator_input: EvaluatorContext
    semantic_tests: dict[str, EvaluationTestConfig]
    semantic_suites: dict[str, TestSuite]
    deterministic_results: dict[str, TestResult]
    reference_answer_used: bool
    selection: TestSelection | None
    jev: JevEvaluation | None


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
    standard_tests = config.get("standard_tests", {})
    if not standard_tests:
        raise ValueError("Evaluation config must define at least one standard test")
    case_tests = config.get("case_tests", {})
    duplicate_names = set(standard_tests) & set(case_tests)
    if duplicate_names:
        raise ValueError(
            f"Case tests duplicate standard tests: {sorted(duplicate_names)}"
        )
    tests = {**standard_tests, **case_tests}
    for name, test in tests.items():
        if not test.get("definition") or not test.get("metric"):
            raise ValueError(f"Evaluation test {name!r} needs a definition and metric")
        if not test.get("evaluator_prompt") and not config.get("evaluator_prompt"):
            raise ValueError(f"Evaluation test {name!r} needs an evaluator prompt")
        if set(test["metric"]) != {"pass", "fail"}:
            raise ValueError(f"Evaluation test {name!r} needs pass and fail metrics")
        for rating, level in test["metric"].items():
            if not level.get("definition"):
                raise ValueError(f"Metric rating {name}.{rating} needs a definition")
    return tests


def _response_message(outputs: Sequence[object]) -> tuple[str, ResponseAction]:
    items = [CompletionOutputItem.model_validate(output) for output in outputs]
    calls = [
        item
        for item in items
        if item.type == "function_call"
    ]
    if len(calls) > 1:
        raise RuntimeError("Tutor returned more than one action")

    if calls:
        call = calls[0]
        if call.name == "conclude_conversation":
            return "[conversation concluded]", "conclude_conversation"
        if call.name != "talk_to_user":
            raise RuntimeError(f"Unsupported tutor tool: {call.name}")
        if call.arguments is None:
            raise RuntimeError("Tutor tool call returned no arguments")
        message = TutorMessageArguments.model_validate_json(
            call.arguments
        ).message_to_user.strip()
    else:
        message = next(
            (
                content.text.strip()
                for item in items
                if item.type == "message"
                for content in item.content
                if content.type == "output_text" and content.text is not None
            ),
            "",
        )

    if not message:
        raise RuntimeError("Tutor returned an empty message")
    return message, "talk_to_user" if calls else "direct_message"


def build_evaluator_request(
    tests: dict[str, EvaluationTestConfig],
    evaluator_input: EvaluatorContext,
) -> EvaluatorRequest:
    """Build the shared OpenAI evaluation payload for selected tests."""
    test_input: EvaluatorRequest = {
        **evaluator_input,
        "tests": [
            {
                "name": name,
                "definition": test["definition"],
                "metric": {
                    rating: level["definition"]
                    for rating, level in test["metric"].items()
                },
                "rules": test.get("evaluator_prompt", "Apply the metric exactly."),
            }
            for name, test in tests.items()
        ],
    }
    return test_input


def parse_evaluator_result(
    evaluation: CombinedEvaluationResult,
    tests: dict[str, EvaluationTestConfig],
    suites: dict[str, TestSuite],
) -> dict[str, TestResult]:
    """Validate and label one OpenAI evaluator response."""
    judgments = evaluation.results
    names = [judgment.name for judgment in judgments]
    if len(names) != len(set(names)) or set(names) != set(tests):
        raise RuntimeError("Evaluator did not return every selected test exactly once")
    return {
        judgment.name: {
            "rating": judgment.rating,
            "evidence": judgment.evidence,
            "rationale": judgment.rationale,
            "suite": suites[judgment.name],
            "evaluator": "openai",
        }
        for judgment in judgments
    }


async def _evaluate_tests(
    *,
    client: EvaluationClient,
    prepared: PreparedEvaluation,
) -> tuple[dict[str, TestResult], str]:
    """Run every JEV-selected semantic test in one OpenAI call."""
    response = await client.responses.parse(
        model=prepared.evaluator_model,
        instructions=prepared.evaluator_prompt,
        input=json.dumps(
            build_evaluator_request(
                prepared.semantic_tests,
                prepared.evaluator_input,
            ),
            indent=2,
        ),
        text_format=CombinedEvaluationResult,
        store=False,
    )
    if response.output_parsed is None:
        raise RuntimeError("Evaluator returned no test results")

    return parse_evaluator_result(
        response.output_parsed,
        prepared.semantic_tests,
        prepared.semantic_suites,
    ), response.model


def _deterministic_results(
    tests: dict[str, RubberDuckTestConfig],
    action: ResponseAction,
) -> dict[str, TestResult]:
    results: dict[str, TestResult] = {}
    for name in tests:
        if name != "message_tool_use":
            raise ValueError(f"No deterministic evaluator exists for {name!r}")
        passed = action in {"talk_to_user", "conclude_conversation"}
        results[name] = {
            "rating": "pass" if passed else "fail",
            "evidence": [action],
            "rationale": (
                "The response used a configured Standard Duck action."
                if passed
                else "The response bypassed the required Standard Duck actions."
            ),
            "suite": "rubber_duck",
            "evaluator": "deterministic",
        }
    return results


def summarize_evaluation(tests: dict[str, TestResult]) -> EvaluationSummary:
    """Calculate deterministic case-level outcomes from configured metrics."""
    return _summarize_ratings(
        {name: result["rating"] for name, result in tests.items()}
    )


def _summarize_ratings(
    ratings: dict[str, TestOutcome],
) -> EvaluationSummary:
    blocking_tests = [
        name for name, rating in ratings.items() if rating == "fail"
    ]
    return {
        "passed": not blocking_tests,
        "score": 1 - len(blocking_tests) / len(ratings),
        "blocking_tests": blocking_tests,
    }


async def prepare_next_response(
    *,
    client: EvaluationClient,
    config: EvaluationConfig,
    transcript: list[TranscriptTurn],
    agent: Agent,
    armory: Armory,
    completion_adapter: ResponsesCompletionAdapter | None = None,
    jev_evaluator: JevEvaluator | None = None,
    rubber_duck_tests: dict[str, RubberDuckTestConfig] | None = None,
) -> PreparedEvaluation:
    """Generate one response and let JEV select its applicable tests."""
    configured_tests = _evaluation_tests(config)
    configured_suites: dict[str, TestSuite] = {
        **{name: "standard" for name in config["standard_tests"]},
        **{name: "case" for name in config.get("case_tests", {})},
    }
    duck_tests = rubber_duck_tests or {}
    duplicate_names = set(configured_tests) & set(duck_tests)
    if duplicate_names:
        raise ValueError(
            f"Rubber Duck tests duplicate configured tests: {sorted(duplicate_names)}"
        )
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
    message, candidate_action = _response_message(completion.output)
    candidate_response: TranscriptTurn = {
        "role": "tutor",
        "message": message,
    }
    evaluator_input: EvaluatorContext = {
        "conversation_prefix": transcript,
        "candidate_response": candidate_response,
        "candidate_action": candidate_action,
        "tutor_prompt": agent.prompt,
    }
    reference_answer = config.get("reference_answer")
    if config.get("use_reference_answer", True) and reference_answer:
        evaluator_input["reference_answer"] = reference_answer

    evaluator_prompt = config.get("evaluator_prompt")
    if evaluator_prompt is None:
        raise ValueError("Combined evaluation needs an evaluator prompt")

    jev_result = None
    selected_duck_tests: dict[str, RubberDuckTestConfig] = {}
    if jev_evaluator is not None:
        jev_result = await jev_evaluator.evaluate(
            evaluator_input,
            configured_tests,
            configured_suites,
            duck_tests,
            config.get("evaluator_prompt"),
        )
        selected_duck_tests = {
            name: duck_tests[name]
            for name in jev_result["selection"]["selected"]
        }

    semantic_duck_tests = {
        name: test
        for name, test in selected_duck_tests.items()
        if test["oracle"] == "semantic"
    }
    deterministic_duck_tests = {
        name: test
        for name, test in selected_duck_tests.items()
        if test["oracle"] == "deterministic"
    }
    semantic_suites: dict[str, TestSuite] = {
        **configured_suites,
        **{name: "rubber_duck" for name in semantic_duck_tests},
    }
    deterministic_results = _deterministic_results(
        deterministic_duck_tests,
        candidate_action,
    )
    return PreparedEvaluation(
        transcript=[*transcript, candidate_response],
        candidate_action=candidate_action,
        candidate_model=completion.provider_model or agent.model,
        evaluator_model=config["evaluator_model"],
        evaluator_prompt=evaluator_prompt,
        evaluator_input=evaluator_input,
        semantic_tests={**configured_tests, **semantic_duck_tests},
        semantic_suites=semantic_suites,
        deterministic_results=deterministic_results,
        reference_answer_used="reference_answer" in evaluator_input,
        selection=jev_result["selection"] if jev_result is not None else None,
        jev=jev_result,
    )


def complete_evaluation(
    prepared: PreparedEvaluation,
    semantic_results: dict[str, TestResult],
    openai_evaluator_model: str,
) -> EvaluationRun:
    """Combine model judgments and exact checks into one evaluation run."""
    if prepared.jev is not None and set(prepared.jev["tests"]) != set(
        semantic_results
    ):
        raise RuntimeError("OpenAI and JEV did not evaluate the same semantic tests")

    tests = {**semantic_results, **prepared.deterministic_results}

    result: EvaluationRun = {
        "transcript": prepared.transcript,
        "candidate_action": prepared.candidate_action,
        "candidate_model": prepared.candidate_model,
        "openai_evaluator_model": openai_evaluator_model,
        "tests": tests,
        "summary": summarize_evaluation(tests),
        "reference_answer_used": prepared.reference_answer_used,
    }
    if prepared.selection is not None:
        result["selection"] = prepared.selection
    if prepared.jev is not None:
        result["jev"] = prepared.jev
    return result


async def evaluate_prepared_response(
    *,
    client: EvaluationClient,
    prepared: PreparedEvaluation,
) -> EvaluationRun:
    """Grade one prepared response synchronously with OpenAI."""
    semantic_results, evaluator_model = await _evaluate_tests(
        client=client,
        prepared=prepared,
    )
    return complete_evaluation(prepared, semantic_results, evaluator_model)


async def evaluate_next_response(
    *,
    client: EvaluationClient,
    config: EvaluationConfig,
    transcript: list[TranscriptTurn],
    agent: Agent,
    armory: Armory,
    completion_adapter: ResponsesCompletionAdapter | None = None,
    jev_evaluator: JevEvaluator | None = None,
    rubber_duck_tests: dict[str, RubberDuckTestConfig] | None = None,
) -> EvaluationRun:
    """Generate, select tests with JEV, and grade one tutor response."""
    prepared = await prepare_next_response(
        client=client,
        config=config,
        transcript=transcript,
        agent=agent,
        armory=armory,
        completion_adapter=completion_adapter,
        jev_evaluator=jev_evaluator,
        rubber_duck_tests=rubber_duck_tests,
    )
    return await evaluate_prepared_response(client=client, prepared=prepared)
