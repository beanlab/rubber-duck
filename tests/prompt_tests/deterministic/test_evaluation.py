"""Test the fixed-prefix evaluation plumbing without live model calls.

The fake client verifies conversation-history conversion, one-response
generation, combined evaluation, evaluator input boundaries, prompt selection,
configured metrics, and deterministic summaries. It does not test
whether a real evaluator's tutoring-quality judgments are valid.
"""

import asyncio
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from src.armory.armory import Armory
from src.armory.talk_tool import TalkTool
from src.gen_ai.gen_ai import Agent
from experiments.evaluation.config import load_evaluation_suite
from experiments.evaluation.engine import (
    build_tutor_history,
    evaluate_next_response,
)
from experiments.evaluation.console import print_prompt_summary
from experiments.evaluation.types import (
    CombinedEvaluationResult,
    EvaluatorRequest,
    RubberDuckTestConfig,
    TranscriptTurn,
)
from tests.prompt_tests.deterministic.support import FakeOpenAIClient


PROMPT_CONFIG_DIRECTORY = Path(__file__).resolve().parents[1] / "configs"


def test_generates_once_and_runs_each_configured_test(
    capsys: pytest.CaptureFixture[str],
) -> None:
    prefix: list[TranscriptTurn] = [
        {"role": "student", "message": "I need help."},
        {"role": "tutor", "message": "What have you tried?"},
        {"role": "student", "message": "I do not know where to start."},
    ]
    shared_config = load_evaluation_suite(PROMPT_CONFIG_DIRECTORY).config
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
    rubber_duck_tests: dict[str, RubberDuckTestConfig] = {
        "concise_response": {
            "selection": "always",
            "definition": "Is the response concise?",
            "metric": {
                "pass": {"definition": "Concise"},
                "fail": {"definition": "Verbose"},
            },
        },
    }

    result = asyncio.run(
        evaluate_next_response(
            client=client,
            config=config,
            transcript=prefix,
            agent=agent,
            armory=armory,
            rubber_duck_tests=rubber_duck_tests,
        )
    )

    assert result["transcript"][-1] == {
        "role": "tutor",
        "message": "What output does the assignment require?",
    }
    assert result["reference_answer_used"] is True
    assert result["candidate_action"] == "talk_to_user"
    assert result["candidate_model"] == "test-model-version"
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
    assert set(result["tests"]) == {
        "factual_correctness",
        "case_actionability",
        "concise_response",
    }
    assert result["tests"]["factual_correctness"]["rating"] == "pass"
    assert result["tests"]["factual_correctness"]["suite"] == "standard"
    assert result["tests"]["case_actionability"]["rating"] == "fail"
    assert result["tests"]["case_actionability"]["suite"] == "case"
    assert result["tests"]["concise_response"]["suite"] == "rubber_duck"
    assert result["summary"] == {
        "passed": False,
        "score": 1 - 1 / 3,
        "blocking_tests": ["case_actionability"],
    }
    assert client.create_input == build_tutor_history(prefix)
    assert len(client.parse_params) == 1
    call = client.parse_params[0]
    evaluator_input = TypeAdapter(EvaluatorRequest).validate_json(call.input)
    assert call.instructions == config.get("evaluator_prompt")
    configured_tests = {
        **config["standard_tests"],
        **config.get("case_tests", {}),
        "concise_response": rubber_duck_tests["concise_response"],
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
