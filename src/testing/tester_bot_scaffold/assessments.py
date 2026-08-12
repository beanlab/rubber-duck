import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from openai.lib._parsing._responses import type_to_text_format_param

from ...gen_ai.gen_ai import Agent, AIClient
from .model_pricing import calculate_token_cost
from ...storage.assessment_models import (
    PostConversationAssessment,
    ProgressAssessment,
)
from ...utils.config_types import DuckContext, HistoryType


ASSESSOR_COSTS_FILENAME = "assessor_costs.csv"


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


def _make_usage_row(
    response,
    assessor: Agent,
    *,
    timestamp: str,
    set_id: str,
    call_number: int,
) -> dict[str, object]:
    usage = response.usage
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cached_tokens = (
        getattr(
            getattr(usage, "input_tokens_details", None),
            "cached_tokens",
            0,
        )
        or 0
    )
    reasoning_tokens = (
        getattr(
            getattr(usage, "output_tokens_details", None),
            "reasoning_tokens",
            0,
        )
        or 0
    )
    cost = calculate_token_cost(
        assessor.model,
        input_tokens,
        output_tokens,
        cached_tokens,
    )

    return {
        "timestamp": timestamp,
        "set_id": set_id,
        "call_number": call_number,
        "assessor_name": assessor.name,
        "model": assessor.model,
        "input_tokens": input_tokens,
        "cached_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "input_cost_usd": cost.input_cost,
        "output_cost_usd": cost.output_cost,
        "total_cost_usd": cost.total,
    }


def _run_metadata() -> tuple[str, str]:
    timestamp = datetime.now(timezone.utc).isoformat()
    current_test = os.getenv("PYTEST_CURRENT_TEST", "").split(" ", 1)[0]
    set_id = current_test.rsplit("::", 1)[-1] if current_test else timestamp
    return timestamp, set_id


async def assess_conversation(
    *,
    ai_client: AIClient,
    history: list[HistoryType],
    assessor: Agent,
    ctx: DuckContext | None = None,
    output_directory: str | Path | None = None,
    close_group: bool = True,
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

    usage_rows = []
    timestamp, set_id = _run_metadata()
    try:
        response = await _request_assessment(ai_client, assessor, formatted_history)
        usage_rows.append(
            _make_usage_row(
                response,
                assessor,
                timestamp=timestamp,
                set_id=set_id,
                call_number=1,
            )
        )
        return PostConversationAssessment.model_validate_json(response.output_text)
    finally:
        if output_directory is not None:
            _append_usage(
                output_directory,
                usage_rows,
                close_group=close_group,
            )


def _append_usage(
    output_directory: str | Path,
    usage_rows: list[dict[str, object]],
    *,
    close_group: bool = True,
) -> None:
    if not usage_rows:
        return

    output_path = Path(output_directory) / ASSESSOR_COSTS_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    has_content = output_path.exists() and output_path.stat().st_size > 0

    with output_path.open("a", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=usage_rows[0].keys(),
        )
        if not has_content:
            writer.writeheader()

        writer.writerows(usage_rows)
        if close_group:
            writer.writerow({})


def append_test_status(
    output_directory: str | Path,
    status: str,
) -> None:
    if status not in {"pass", "fail"}:
        raise ValueError(f"Unsupported test status: {status}")

    output_path = Path(output_directory) / ASSESSOR_COSTS_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8", newline="") as output_file:
        output_file.write(f"===prev_{status}===\n\n")


async def assess_conversations(
    *,
    ai_client: AIClient,
    history: list[HistoryType],
    assessors: list[Agent],
    output_directory: str | Path,
    close_group: bool = True,
) -> list[PostConversationAssessment]:
    formatted_history = format_history_for_assessor(history)
    assessments = []
    usage_rows = []
    timestamp, set_id = _run_metadata()

    try:
        for call_number, assessor in enumerate(assessors, start=1):
            response = await _request_assessment(
                ai_client,
                assessor,
                formatted_history,
            )

            usage_rows.append(
                _make_usage_row(
                    response,
                    assessor,
                    timestamp=timestamp,
                    set_id=set_id,
                    call_number=call_number,
                )
            )

            assessments.append(
                PostConversationAssessment.model_validate_json(
                    response.output_text
                )
            )
    finally:
        _append_usage(
            output_directory,
            usage_rows,
            close_group=close_group,
        )

    return assessments
