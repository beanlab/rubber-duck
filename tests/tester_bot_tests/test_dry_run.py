"""Live standard-duck dry run using the shared criterion evaluator."""

from pathlib import Path

import pytest
import yaml

from src.testing.prompt_evaluation import (
    OpenAIModel,
    evaluate_transcript,
    print_evaluation,
)


TEST_ROOT = Path(__file__).resolve().parent
ROOT = TEST_ROOT.parents[1]
PROMPT = TEST_ROOT / "prompts" / "standard_duck" / "dry-run.md"
EVALUATION_CONFIG = ROOT / "evaluation_assets" / "prompt_eval.yaml"

CLOSED_MESSAGE = "*This conversation has been closed.*"
ERROR_MARKER = "😵 **Error code"


def history_text(history) -> str:
    return "\n".join(str(item) for item in history)


def assert_closed_without_error(history) -> None:
    text = history_text(history)
    assert CLOSED_MESSAGE in text, "Conversation did not reach the duck close message."
    assert ERROR_MARKER not in text, "Conversation hit the duck orchestrator error path."


def _message_text(item: dict) -> str:
    content = item.get("content", "")
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", part)) if isinstance(part, dict) else str(part)
            for part in content
        ).strip()
    return str(content).strip()


def transcript_from_tester_history(history: list[dict]) -> list[dict[str, str]]:
    """Translate TesterBot roles into student/tutor roles for the evaluator."""
    transcript = []
    for item in history:
        if item.get("type") != "message":
            continue
        message = _message_text(item)
        if not message:
            continue
        role = {"user": "tutor", "assistant": "student"}.get(item.get("role"))
        if role:
            transcript.append({"role": role, "message": message})
    return transcript


@pytest.mark.anyio
async def test_standard_duck_dry_run(
    testerbot,
    duck_channel_id,
    report_conversation_cost,
):
    history = await testerbot.run_conversation(
        channel_id=duck_channel_id("standard-rubber-duck"),
        thread_opener="Dry run: STANDARD RUBBER DUCK",
        base_prompt=PROMPT.read_text(encoding="utf-8"),
        max_turns=30,
        idle_timeout_seconds=30,
    )
    assert_closed_without_error(history)
    report_conversation_cost(testerbot)

    config = yaml.safe_load(EVALUATION_CONFIG.read_text(encoding="utf-8"))
    config["use_reference_answer"] = False
    tutor_prompt = (ROOT / config["prompt_path"]).read_text(encoding="utf-8")
    result = await evaluate_transcript(
        config=config,
        model_client=OpenAIModel(testerbot.ai_client._client),
        transcript=transcript_from_tester_history(history),
        tutor_prompt=tutor_prompt,
    )

    print_evaluation(result)
    assert set(result["criteria"]) == set(config["criteria"])
