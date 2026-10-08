"""OpenAI Batch grading for JEV-selected prompt evaluation tests."""

import asyncio
import json
from collections.abc import Sequence
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, TypeAdapter
from typing_extensions import TypedDict

from src.testing.prompt_evaluation.evaluation import (
    PreparedEvaluation,
    build_evaluator_request,
    complete_evaluation,
    parse_evaluator_result,
)
from src.testing.prompt_evaluation.types import (
    CombinedEvaluationResult,
    EvaluationRun,
)


class BatchRequestLine(TypedDict):
    custom_id: str
    method: Literal["POST"]
    url: Literal["/v1/responses"]
    body: dict[str, object]


class BatchOutputContent(BaseModel):
    type: str
    text: str | None = None


class BatchOutputItem(BaseModel):
    type: str
    content: list[BatchOutputContent] = Field(default_factory=list)


class BatchResponseBody(BaseModel):
    model: str
    output: list[BatchOutputItem]


class BatchHTTPResponse(BaseModel):
    status_code: int
    body: BatchResponseBody


class BatchOutputLine(BaseModel):
    custom_id: str
    response: BatchHTTPResponse | None = None
    error: object | None = None


TERMINAL_STATUSES = {"completed", "failed", "expired", "cancelled"}


def build_batch_input(prepared: Sequence[PreparedEvaluation]) -> bytes:
    """Build one Responses API batch request per prepared case."""
    if not prepared:
        raise ValueError("At least one prepared evaluation is required")
    models = {item.evaluator_model for item in prepared}
    if len(models) != 1:
        raise ValueError("One OpenAI batch input file can target only one model")

    schema = TypeAdapter(dict[str, object]).validate_python(
        CombinedEvaluationResult.model_json_schema()
    )
    lines: list[str] = []
    for index, item in enumerate(prepared):
        request: BatchRequestLine = {
            "custom_id": f"case-{index}",
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": item.evaluator_model,
                "instructions": item.evaluator_prompt,
                "input": json.dumps(
                    build_evaluator_request(
                        item.semantic_tests,
                        item.evaluator_input,
                    ),
                    indent=2,
                ),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "CombinedEvaluationResult",
                        "strict": True,
                        "schema": schema,
                    }
                },
                "store": False,
            },
        }
        lines.append(json.dumps(request))
    return ("\n".join(lines) + "\n").encode()


async def evaluate_openai_batch(
    client: AsyncOpenAI,
    prepared: Sequence[PreparedEvaluation],
    *,
    poll_seconds: float = 10,
) -> list[EvaluationRun]:
    """Submit, await, and parse one OpenAI grading batch."""
    if poll_seconds <= 0 or poll_seconds > 60:
        raise ValueError("poll_seconds must be greater than 0 and at most 60")

    input_file = await client.files.create(
        file=(
            "prompt-evaluation.jsonl",
            build_batch_input(prepared),
            "application/jsonl",
        ),
        purpose="batch",
    )
    batch = await client.batches.create(
        input_file_id=input_file.id,
        endpoint="/v1/responses",
        completion_window="24h",
        metadata={"description": "Rubber Duck prompt evaluation"},
    )
    print(f"OpenAI evaluation batch submitted: {batch.id}")

    last_status = batch.status
    print(f"OpenAI evaluation batch status: {last_status}")
    while batch.status not in TERMINAL_STATUSES:
        await asyncio.sleep(poll_seconds)
        batch = await client.batches.retrieve(batch.id)
        if batch.status != last_status:
            last_status = batch.status
            print(f"OpenAI evaluation batch status: {last_status}")

    if batch.status != "completed" or batch.output_file_id is None:
        raise RuntimeError(
            f"OpenAI evaluation batch {batch.id} ended with {batch.status}"
        )

    output = await client.files.content(batch.output_file_id)
    lines = [
        BatchOutputLine.model_validate_json(line)
        for line in output.text.splitlines()
        if line.strip()
    ]
    indexed = {_batch_index(line.custom_id): line for line in lines}
    if set(indexed) != set(range(len(prepared))):
        raise RuntimeError("OpenAI batch did not return every evaluation case")

    results: list[EvaluationRun] = []
    for index, item in enumerate(prepared):
        line = indexed[index]
        if line.response is None or line.response.status_code != 200:
            raise RuntimeError(
                f"OpenAI batch evaluation failed for {line.custom_id}: {line.error}"
            )
        body = line.response.body
        evaluation = CombinedEvaluationResult.model_validate_json(
            _output_text(body.output)
        )
        semantic_results = parse_evaluator_result(
            evaluation,
            item.semantic_tests,
            item.semantic_suites,
        )
        results.append(complete_evaluation(item, semantic_results, body.model))
    return results


def _batch_index(custom_id: str) -> int:
    prefix = "case-"
    if not custom_id.startswith(prefix):
        raise RuntimeError(f"Unknown OpenAI batch custom ID: {custom_id}")
    return int(custom_id.removeprefix(prefix))


def _output_text(items: list[BatchOutputItem]) -> str:
    texts = [
        content.text
        for item in items
        if item.type == "message"
        for content in item.content
        if content.type == "output_text" and content.text is not None
    ]
    if len(texts) != 1:
        raise RuntimeError("OpenAI batch evaluator returned no unique output text")
    return texts[0]
