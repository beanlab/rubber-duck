from pathlib import Path

import pytest

TESTER_BOT_TESTS_ROOT = Path(__file__).resolve().parent
PROMPTS_ROOT = TESTER_BOT_TESTS_ROOT / "prompts"

CLOSED_MESSAGE = "*This conversation has been closed.*"
ERROR_MARKER = "😵 **Error code"


def history_text(history) -> str:
    return "\n".join(str(item) for item in history)


def assert_closed_without_error(history) -> None:
    text = history_text(history)
    assert CLOSED_MESSAGE in text, "Conversation did not reach the duck close message."
    assert ERROR_MARKER not in text, "Conversation hit the duck orchestrator error path."


@pytest.mark.anyio
async def test_standard_duck_dry_run(testerbot, duck_channel_id):
    history = await testerbot.run_conversation(
        channel_id=duck_channel_id("standard-rubber-duck"),
        thread_opener="Dry run: STANDARD RUBBER DUCK",
        base_prompt=(PROMPTS_ROOT / "standard_duck" / "dry-run.md").read_text(),
        max_turns=30,
        idle_timeout_seconds=30,
    )

    assert_closed_without_error(history)


@pytest.mark.anyio
async def test_stats_duck_dry_run(testerbot, duck_channel_id):
    history = await testerbot.run_conversation(
        channel_id=duck_channel_id("cs-stats-duck"),
        thread_opener="Dry run: CS STATS DUCK",
        base_prompt=(PROMPTS_ROOT / "stats_duck" / "dry-run.md").read_text(),
        max_turns=30,
        idle_timeout_seconds=60,
    )

    assert_closed_without_error(history)


@pytest.mark.anyio
async def test_debugging_duck_dry_run(testerbot, duck_channel_id):
    history = await testerbot.run_conversation(
        channel_id=duck_channel_id("debugging-practice-duck"),
        thread_opener="Dry run: DEBUGGING PRACTICE DUCK",
        base_prompt=(PROMPTS_ROOT / "debugging_practice_duck" / "dry_run.md").read_text(),
        max_turns=60,
        idle_timeout_seconds=30,
    )

    assert_closed_without_error(history)
