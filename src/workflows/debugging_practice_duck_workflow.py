import asyncio
from dataclasses import replace
from typing import Any, Literal

from ..gen_ai.gen_ai import AIClient, Agent
from ..utils.config_types import DebuggingPracticeDuckSettings, DuckContext
from ..utils.message_utils import wait_for_message
from ..utils.protocols import ConversationComplete
from .debugging_context import (
    ConversationTurn,
    record_student_message,
    record_ta_message,
    render_assessor_prompt,
    render_completion_prompt,
)
from .debugging_completions import (
    DEBUGGING_PRACTICE_FEEDBACK_MESSAGE,
    build_completion_message,
    build_incomplete_response_message,
    build_incorrect_response_message,
    build_next_exercise_message,
    build_opening_message,
    build_unrelated_response_message,
    priority_prompt_for_item,
)
from .debugging_parsing import (
    PRIORITY_ORDER,
    build_rubric_state,
    load_rubric_files,
    parse_debugging_response,
)


ExerciseStatus = Literal["item_complete", "exercise_complete"]
AssessmentStatus = Literal["complete", "incomplete", "incorrect", "unattempted"]
AssessmentPackage = dict[str, AssessmentStatus | bool]


async def run_agent(
        ai_client: AIClient,
        context: DuckContext,
        agent: Agent,
        prompt_context: str,
):
    return await ai_client.run_agent(context, agent, prompt_context)


async def wait_for_user_response(context: DuckContext) -> str:
    message = await wait_for_message(context.timeout)
    if message is None:
        raise ConversationComplete("This conversation has timed out.")
    return message["content"]


async def review_priority(
        ai_client: AIClient,
        context: DuckContext,
        priority_agent: Agent,
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
        priority_key: str,
) -> dict[str, Any]:
    rendered_prompt = render_assessor_prompt(
        priority_agent.prompt,
        exercise,
        conversation_context,
        "priority_assessment",
    )
    raw_response = await run_agent(
        ai_client,
        context,
        replace(priority_agent, prompt=rendered_prompt),
        f"Assess the latest TA response for {priority_key}.",
    )
    return parse_debugging_response(raw_response, "priority_assessment")


async def review_unrelated_assessment(
        ai_client: AIClient,
        context: DuckContext,
        unrelated_assessor: Agent,
        rubric: dict[str, Any],
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
) -> dict[str, Any]:
    rendered_prompt = render_assessor_prompt(
        unrelated_assessor.prompt,
        exercise,
        conversation_context,
        "unrelated_assessment",
        rubric=rubric,
    )
    raw_response = await run_agent(
        ai_client,
        context,
        replace(unrelated_assessor, prompt=rendered_prompt),
        "Assess whether the latest TA response is unrelated.",
    )
    return parse_debugging_response(raw_response, "unrelated_assessment")


async def collect_assessments(
        ai_client: AIClient,
        context: DuckContext,
        rubric: dict[str, Any],
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
        assessor_agents: dict[str, Agent],
) -> AssessmentPackage:
    async def collect():
        tasks = [
            asyncio.create_task(
                review_priority(
                    ai_client,
                    context,
                    assessor_agents[priority_key],
                    exercise,
                    conversation_context,
                    priority_key,
                )
            )
            for priority_key in PRIORITY_ORDER
        ]
        unrelated_task = asyncio.create_task(
            review_unrelated_assessment(
                ai_client,
                context,
                assessor_agents["unrelated"],
                rubric,
                exercise,
                conversation_context,
            )
        )
        return await asyncio.gather(*tasks, unrelated_task)

    *priority_results, unrelated_result = await collect()
    packaged: AssessmentPackage = {
        priority_key: priority_results[index]["status"]
        for index, priority_key in enumerate(PRIORITY_ORDER)
    }
    packaged["unrelated"] = unrelated_result["unrelated"]
    return packaged


async def review_incomplete_response(
        ai_client: AIClient,
        context: DuckContext,
        incomplete_agent: Agent,
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
        priority_key: str | None = None,
) -> dict[str, Any]:
    rendered_prompt = render_completion_prompt(
        incomplete_agent.prompt,
        "incomplete_response",
        exercise,
        conversation_context,
        priority_key=priority_key,
    )
    raw_response = await run_agent(
        ai_client,
        context,
        replace(incomplete_agent, prompt=rendered_prompt),
        "Build an incomplete-response completion for the latest TA response.",
    )
    return parse_debugging_response(raw_response, "incomplete_response")


async def review_unrelated_response(
        ai_client: AIClient,
        context: DuckContext,
        unrelated_agent: Agent,
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
) -> dict[str, Any]:
    rendered_prompt = render_completion_prompt(
        unrelated_agent.prompt,
        "unrelated_completion",
        exercise,
        conversation_context,
    )
    raw_response = await run_agent(
        ai_client,
        context,
        replace(unrelated_agent, prompt=rendered_prompt),
        "Build an unrelated-response completion for the latest TA response.",
    )
    return parse_debugging_response(raw_response, "unrelated_completion")


async def review_incorrect_response(
        ai_client: AIClient,
        context: DuckContext,
        incorrect_agent: Agent,
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
        priority_key: str,
) -> dict[str, Any]:
    rendered_prompt = render_completion_prompt(
        incorrect_agent.prompt,
        "incorrect_response",
        exercise,
        conversation_context,
        priority_key=priority_key,
    )
    raw_response = await run_agent(
        ai_client,
        context,
        replace(incorrect_agent, prompt=rendered_prompt),
        "Build an incorrect-response support completion for the latest TA response.",
    )
    return parse_debugging_response(raw_response, "incorrect_response")


async def send_student_message(
        context: DuckContext,
        send_message,
        conversation_context: list[ConversationTurn],
        response: str,
) -> None:
    record_student_message(conversation_context, response)
    await send_message(context.thread_id, response)


async def initialize_debugging_session(
        context: DuckContext,
        settings: DebuggingPracticeDuckSettings,
        send_message,
) -> tuple[list[ConversationTurn], dict[str, Any]]:
    conversation_context: list[ConversationTurn] = []
    rubric = build_rubric_state(load_rubric_files(settings))

    opening_message = build_opening_message(settings)
    await send_student_message(
        context,
        send_message,
        conversation_context,
        opening_message,
    )
    return conversation_context, rubric


async def finish_rubric(
        context: DuckContext,
        conversation_context: list[ConversationTurn],
        send_message,
) -> None:
    next_message = build_completion_message()
    await send_student_message(
        context,
        send_message,
        conversation_context,
        next_message["response"],
    )
    await send_message(
        context.thread_id,
        DEBUGGING_PRACTICE_FEEDBACK_MESSAGE,
    )


async def send_exercise_context(
        context: DuckContext,
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
        send_message,
        completed_previous: bool = False,
) -> None:
    next_message = build_next_exercise_message(exercise, completed_previous)
    await send_student_message(
        context,
        send_message,
        conversation_context,
        next_message["response"],
    )


async def process_incorrect_response(
        ai_client: AIClient,
        context: DuckContext,
        exercise: dict[str, Any],
        conversation_context: list[ConversationTurn],
        incorrect_agent: Agent,
        priority_key: str,
) -> dict[str, Any]:
    completion = await review_incorrect_response(
        ai_client,
        context,
        incorrect_agent,
        exercise,
        conversation_context,
        priority_key,
    )
    if not completion["concept_understood"]:
        return build_incorrect_response_message(
            completion,
            exercise,
            priority_key,
        )

    return {
        "response": priority_prompt_for_item(priority_key, exercise),
    }


def exercise_done(status: AssessmentPackage) -> bool:
    priority_complete = all(
        status[priority_key] == "complete"
        for priority_key in PRIORITY_ORDER
    )
    concept_and_fix_complete = (
        status["concept"] == "complete"
        and status["fix"] == "complete"
    )
    return priority_complete or concept_and_fix_complete


def goal_done(status: AssessmentPackage, goal: str) -> bool:
    return not status["unrelated"] and (
        exercise_done(status)
        or status[goal] == "complete"
    )


async def send_and_record(
        context: DuckContext,
        send_message,
        conversation_context: list[ConversationTurn],
        response: str,
) -> None:
    await send_student_message(
        context,
        send_message,
        conversation_context,
        response,
    )
    user_response = await wait_for_user_response(context)
    record_ta_message(conversation_context, user_response)


async def next_goal(
        ai_client: AIClient,
        context: DuckContext,
        rubric: dict[str, Any],
        exercise: dict[str, Any],
        goal: str,
        conversation_context: list[ConversationTurn],
        assessor_agents: dict[str, Agent],
        incomplete_agent: Agent,
        unrelated_agent: Agent,
        incorrect_agent: Agent,
        send_message,
) -> AssessmentPackage:
    grace = 1
    await send_and_record(
        context,
        send_message,
        conversation_context,
        priority_prompt_for_item(goal, exercise),
    )

    while not goal_done(
        status := await collect_assessments(
            ai_client,
            context,
            rubric,
            exercise,
            conversation_context,
            assessor_agents,
        ),
        goal,
    ):
        if status["unrelated"]:
            completion = await review_unrelated_response(
                ai_client,
                context,
                unrelated_agent,
                exercise,
                conversation_context,
            )
            next_message = build_unrelated_response_message(completion)
        elif status[goal] == "incomplete" and grace:
            grace -= 1
            decision = await review_incomplete_response(
                ai_client,
                context,
                incomplete_agent,
                exercise,
                conversation_context,
                goal,
            )
            next_message = build_incomplete_response_message(decision)
        elif status[goal] == "incorrect" or (status[goal] == "incomplete" and not grace):
            next_message = await process_incorrect_response(
                ai_client,
                context,
                exercise,
                conversation_context,
                incorrect_agent,
                goal,
            )
        elif status[goal] == "unattempted":
            next_message = {
                "response": priority_prompt_for_item(goal, exercise),
            }
        else:
            raise ValueError(f"Unsupported assessment status: {status[goal]}")

        await send_and_record(
            context,
            send_message,
            conversation_context,
            next_message["response"],
        )

    return status


async def rubric_run(
        ai_client: AIClient,
        context: DuckContext,
        rubric: dict[str, Any],
        priorities: list[str],
        conversation_context: list[ConversationTurn],
        assessor_agents: dict[str, Agent],
        incomplete_agent: Agent,
        unrelated_agent: Agent,
        incorrect_agent: Agent,
        send_message,
) -> None:
    for exercise_index, exercise in enumerate(rubric["exercises"]):
        await send_exercise_context(
            context,
            exercise,
            conversation_context,
            send_message,
            completed_previous=exercise_index > 0,
        )

        status: AssessmentPackage | None = None
        for goal in priorities:
            if status is not None and status[goal] == "complete":
                continue
            status = await next_goal(
                ai_client,
                context,
                rubric,
                exercise,
                goal,
                conversation_context,
                assessor_agents,
                incomplete_agent,
                unrelated_agent,
                incorrect_agent,
                send_message,
            )
            if exercise_done(status):
                break

    await finish_rubric(
        context,
        conversation_context,
        send_message,
    )


async def debugging_practice_duck(
        context: DuckContext,
        settings: DebuggingPracticeDuckSettings,
        ai_client: AIClient,
        assessor_agents: dict[str, Agent],
        incomplete_agent: Agent,
        unrelated_agent: Agent,
        incorrect_agent: Agent,
        send_message,
) -> None:
    try:
        conversation_context, rubric = await initialize_debugging_session(
            context,
            settings,
            send_message,
        )

        await rubric_run(
            ai_client,
            context,
            rubric,
            PRIORITY_ORDER,
            conversation_context,
            assessor_agents,
            incomplete_agent,
            unrelated_agent,
            incorrect_agent,
            send_message,
        )

    except ConversationComplete as error:
        if str(error):
            await send_message(context.thread_id, str(error))


def build_debugging_practice_duck(
        name: str,
        send_message,
        settings: DebuggingPracticeDuckSettings,
        assessor_agents: dict[str, Agent],
        ai_client: AIClient,
        incomplete_subprocess: Agent | None = None,
        incorrect_subprocess: Agent | None = None,
        unrelated_subprocess: Agent | None = None,
):
    missing_assessors = [
        assessor_name
        for assessor_name in [*PRIORITY_ORDER, "unrelated"]
        if assessor_name not in assessor_agents
    ]
    if missing_assessors:
        raise ValueError(
            "debugging_practice_duck requires assessor agents in config: "
            + ", ".join(missing_assessors)
        )
    if incomplete_subprocess is None:
        raise ValueError(
            "debugging_practice_duck requires an incomplete_subprocess agent in config")
    if incorrect_subprocess is None:
        raise ValueError(
            "debugging_practice_duck requires an incorrect_subprocess agent in config")
    if unrelated_subprocess is None:
        raise ValueError(
            "debugging_practice_duck requires an unrelated_subprocess agent in config")

    incomplete_agent = incomplete_subprocess
    unrelated_agent = unrelated_subprocess
    incorrect_agent = incorrect_subprocess

    async def duck(context: DuckContext):
        await debugging_practice_duck(
            context,
            settings,
            ai_client,
            assessor_agents,
            incomplete_agent,
            unrelated_agent,
            incorrect_agent,
            send_message,
        )

    duck.name = name
    return duck


class DebuggingPracticeDuckWorkflow:
    def __init__(
            self,
            name: str,
            send_message,
            settings: DebuggingPracticeDuckSettings,
            assessor_agents: dict[str, Agent],
            ai_client: AIClient,
            incomplete_subprocess: Agent | None = None,
            incorrect_subprocess: Agent | None = None,
            unrelated_subprocess: Agent | None = None,
    ):
        self.name = name
        self._duck = build_debugging_practice_duck(
            name,
            send_message,
            settings,
            assessor_agents,
            ai_client,
            incomplete_subprocess,
            incorrect_subprocess,
            unrelated_subprocess,
        )

    async def __call__(self, context: DuckContext):
        await self._duck(context)
