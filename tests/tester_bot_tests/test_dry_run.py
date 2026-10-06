import json
from pathlib import Path

import pytest

from src.gen_ai.gen_ai import Agent
from src.storage.assessment_models import PostConversationAssessment
from src.testing.tester_bot_scaffold.assessments import (
    assess_conversation,
    assess_conversations,
    split_assessor_prompt,
)

TESTER_BOT_TESTS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = TESTER_BOT_TESTS_ROOT.parents[1]
PROMPTS_ROOT = TESTER_BOT_TESTS_ROOT / "prompts"
ASSESSORS_ROOT = PROMPTS_ROOT / "assessors"
DEBUGGING_RUBRIC = (REPOSITORY_ROOT / "rubrics" / "CS110" / "3b-rubric.yaml").read_text(
    encoding="utf-8"
)
ASSESSOR_MODEL = "gpt-5.6-luna"

CLOSED_MESSAGE = "*This conversation has been closed.*"
ERROR_MARKER = "😵 **Error code"


def history_text(history) -> str:
    return "\n".join(str(item) for item in history)


def assert_closed_without_error(history) -> None:
    text = history_text(history)
    assert CLOSED_MESSAGE in text, "Conversation did not reach the duck close message."
    assert ERROR_MARKER not in text, "Conversation hit the duck orchestrator error path."


def make_flat_assessor(filename: str) -> Agent:
    prompt = (ASSESSORS_ROOT / filename).read_text(encoding="utf-8")
    prompt = split_assessor_prompt(prompt, battery=False)[0]
    prompt = prompt.replace(
        "{{output_contract}}",
        json.dumps(PostConversationAssessment.model_json_schema(), indent=2),
    )
    return Agent(
        name=Path(filename).stem,
        prompt=prompt,
        model=ASSESSOR_MODEL,
        tools=[],
    )


def make_battery_assessor(filename: str) -> list[Agent]:
    prompt = (ASSESSORS_ROOT / filename).read_text(encoding="utf-8")
    output_contract = json.dumps(
        PostConversationAssessment.model_json_schema(), indent=2
    )
    name = Path(filename).stem
    return [
        Agent(
            name=f"{name}_{index}",
            prompt=prompt_part.replace("{{output_contract}}", output_contract).replace(
                "{{rubric}}", DEBUGGING_RUBRIC
            ),
            model=ASSESSOR_MODEL,
            tools=[],
        )
        for index, prompt_part in enumerate(
            split_assessor_prompt(prompt, battery=True), start=1
        )
    ]


STANDARD_POST_CONVERSATION_ASSESSOR = make_flat_assessor("standard_assessor.md")
STATS_POST_CONVERSATION_ASSESSOR = make_flat_assessor("stats_assessor.md")
DEBUGGING_POST_CONVERSATION_ASSESSOR = make_battery_assessor(
    "debugging_assessor.md"
)


async def assess_history(
    testerbot, history, assessor: Agent | list[Agent]
) -> PostConversationAssessment | list[PostConversationAssessment]:
    if testerbot.last_context is None:
        raise AssertionError(
            "TesterBot did not create a DuckContext for the conversation.")
    if isinstance(assessor, list):
        return await assess_conversations(
            ai_client=testerbot.ai_client,
            ctx=testerbot.last_context,
            history=history,
            assessors=assessor,
        )
    return await assess_conversation(
        ai_client=testerbot.ai_client,
        ctx=testerbot.last_context,
        history=history,
        assessor=assessor,
    )


@pytest.mark.anyio
async def test_standard_duck_dry_run(testerbot, duck_channel_id, report_conversation_cost):
    history = await testerbot.run_conversation(
        channel_id=duck_channel_id("standard-rubber-duck"),
        thread_opener="Dry run: STANDARD RUBBER DUCK",
        base_prompt=(PROMPTS_ROOT / "standard_duck" /
                     "dry-run.md").read_text(),
        max_turns=30,
        idle_timeout_seconds=30,
    )
    assert_closed_without_error(history)
    report_conversation_cost(testerbot)
    assessment = await assess_history(
        testerbot, history, STANDARD_POST_CONVERSATION_ASSESSOR
    )
    assert assessment.status == "pass", assessment.reasoning


@pytest.mark.anyio
async def test_gen_stats_duck_dry_run(testerbot, duck_channel_id, report_conversation_cost):
    history = await testerbot.run_conversation(
        channel_id=duck_channel_id("stats-duck"),
        thread_opener="Dry run: GEN STATS DUCK",
        base_prompt=(PROMPTS_ROOT / "stats_duck" / "dry-run.md").read_text(),
        max_turns=30,
        idle_timeout_seconds=60,
    )
    assert_closed_without_error(history)
    report_conversation_cost(testerbot)
    assessment = await assess_history(
        testerbot, history, STATS_POST_CONVERSATION_ASSESSOR
    )
    assert assessment.status == "pass", assessment.reasoning


@pytest.mark.anyio
async def test_cs_stats_duck_dry_run(testerbot, duck_channel_id, report_conversation_cost):
    history = await testerbot.run_conversation(
        channel_id=duck_channel_id("cs-stats-duck"),
        thread_opener="Dry run: CS STATS DUCK",
        base_prompt=(PROMPTS_ROOT / "stats_duck" / "dry-run.md").read_text(),
        max_turns=30,
        idle_timeout_seconds=60,
    )
    assert_closed_without_error(history)
    report_conversation_cost(testerbot)
    assessment = await assess_history(
        testerbot, history, STATS_POST_CONVERSATION_ASSESSOR
    )
    assert assessment.status == "pass", assessment.reasoning


@pytest.mark.anyio
async def test_debugging_duck_dry_run(testerbot, duck_channel_id, report_conversation_cost):
    history = await testerbot.run_conversation(
        channel_id=duck_channel_id("debugging-practice-duck"),
        thread_opener="Dry run: DEBUGGING PRACTICE DUCK",
        base_prompt=(
            PROMPTS_ROOT / "debugging_practice_duck" / "dry_run.md"
        ).read_text(),
        max_turns=120,
        idle_timeout_seconds=60,
    )
    assert_closed_without_error(history)
    report_conversation_cost(testerbot)
    assessments = await assess_history(
        testerbot, history, DEBUGGING_POST_CONVERSATION_ASSESSOR
    )
    failures = [
        f"{assessor.name}: {assessment.reasoning}"
        for assessor, assessment in zip(
            DEBUGGING_POST_CONVERSATION_ASSESSOR, assessments
        )
        if assessment.status != "pass"
    ]
    assert not failures, "\n\n".join(failures)
