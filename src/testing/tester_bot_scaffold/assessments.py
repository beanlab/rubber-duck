import asyncio
import json
import re
from pathlib import Path

from openai.lib._parsing._responses import type_to_text_format_param

from ...gen_ai.gen_ai import Agent, AIClient
from ...storage.assessment_models import (
    PostConversationAssessment,
    ProgressAssessment,
)
from ...utils.config_types import DuckContext, HistoryType


_ASSESSOR_MARKER_RE = re.compile(r"\{\{\s*(/?)assessor\s*\}\}")


def split_assessor_prompt(prompt: str, *, battery: bool = False) -> list[str]:
    """Split or normalize a prompt containing assessor blocks.

    Text outside ``{{assessor}}``/``{{/assessor}}`` blocks is shared by every
    generated prompt. When ``battery`` is false, the markers are removed and
    all prompt content is returned as one prompt.
    """
    parts: list[tuple[str, str]] = []
    cursor = 0
    open_block = False
    item_parts: list[str] = []

    for match in _ASSESSOR_MARKER_RE.finditer(prompt):
        text = prompt[cursor:match.start()]
        is_close = bool(match.group(1))

        if is_close:
            if not open_block:
                raise ValueError("Found {{/assessor}} without {{assessor}}.")
            item_parts.append(text)
            parts.append(("item", "".join(item_parts)))
            item_parts = []
            open_block = False
        else:
            if open_block:
                raise ValueError("Nested {{assessor}} blocks are not supported.")
            parts.append(("shared", text))
            open_block = True

        cursor = match.end()

    if open_block:
        raise ValueError("Unclosed {{assessor}} block.")

    if not parts:
        return [prompt]

    parts.append(("shared", prompt[cursor:]))
    if not battery:
        return ["".join(text for _, text in parts)]

    item_count = sum(kind == "item" for kind, _ in parts)
    prompts = []
    for item_index in range(item_count):
        item_number = 0
        prompt_parts = []
        for kind, text in parts:
            if kind == "shared":
                prompt_parts.append(text)
            elif item_number == item_index:
                prompt_parts.append(text)
                item_number += 1
            else:
                item_number += 1
        prompts.append("".join(prompt_parts))

    return prompts


def make_agents(source: str | list[str | Path], model: str) -> list[Agent]:
    prompt_paths = (
        sorted(Path(source).glob("*.md"))
        if isinstance(source, str)
        else [Path(prompt) for prompt in source]
    )
    return [
        Agent(name=path.stem, prompt=path.read_text(encoding="utf-8"), model=model, tools=[])
        for path in prompt_paths
    ]


def format_history_for_assessor(history: list[HistoryType]) -> str:
    lines = []
    for item in history:
        if item.get("type") != "message":
            continue

        raw_content = item.get("content", "")
        if isinstance(raw_content, list):
            content = "\n".join(
                str(part.get("text", part)) if isinstance(part, dict) else str(part)
                for part in raw_content
            ).strip()
        else:
            content = str(raw_content).strip()

        if not content:
            continue

        role = str(item.get("role", "")).lower() or "unknown"
        role = {
            "user": "duck",
            "assistant": "tester",
        }.get(role, role)
        lines.append(f"{role}: {content}")

    return "\n\n".join(lines)


def _assessment_params(assessor: Agent, formatted_history: str) -> dict:
    params = {
        "model": assessor.model,
        "instructions": assessor.prompt,
        "input": formatted_history,
        "text": type_to_text_format_param(PostConversationAssessment),
    }
    if assessor.reasoning:
        params["reasoning"] = {"effort": assessor.reasoning}
    return params


async def _request_assessment(
    ai_client: AIClient,
    assessor: Agent,
    formatted_history: str,
):
    return await ai_client._client.responses.create(
        **_assessment_params(assessor, formatted_history)
    )


async def assess_prompt(
    *,
    ai_client: AIClient,
    history: list[HistoryType],
    prompt: str,
    model: str,
    ctx: DuckContext | None = None,
    name: str = "assessor",
    reasoning: str | None = None,
    battery: bool = False,
) -> list[PostConversationAssessment]:
    """Assess a conversation with one prompt or a marked assessor battery."""
    prompt_parts = split_assessor_prompt(prompt, battery=battery)
    output_contract = json.dumps(
        PostConversationAssessment.model_json_schema(),
        indent=2,
    )
    assessors = [
        Agent(
            name=f"{name}_{index}",
            prompt=prompt_part.replace("{{output_contract}}", output_contract),
            model=model,
            tools=[],
            reasoning=reasoning,
        )
        for index, prompt_part in enumerate(prompt_parts, start=1)
    ]

    return list(
        await asyncio.gather(
            *(
                assess_conversation(
                    ai_client=ai_client,
                    history=history,
                    assessor=assessor,
                    ctx=ctx,
                )
                for assessor in assessors
            )
        )
    )


async def assess_conversation(
    *,
    ai_client: AIClient,
    history: list[HistoryType],
    assessor: Agent,
    ctx: DuckContext | None = None,
) -> PostConversationAssessment:
    formatted_history = format_history_for_assessor(history)

    if ctx is not None:
        assessment = await ai_client.run_agent(
            ctx,
            assessor,
            formatted_history,
            output_format=PostConversationAssessment,
        )
        return assessment

    response = await _request_assessment(ai_client, assessor, formatted_history)
    return PostConversationAssessment.model_validate_json(response.output_text)


async def assess_conversations(
    *,
    ai_client: AIClient,
    history: list[HistoryType],
    assessors: list[Agent],
    ctx: DuckContext | None = None,
) -> list[PostConversationAssessment]:
    """Run multiple assessors concurrently and return their results."""
    return list(
        await asyncio.gather(
            *(
                assess_conversation(
                    ai_client=ai_client,
                    history=history,
                    assessor=assessor,
                    ctx=ctx,
                )
                for assessor in assessors
            )
        )
    )
