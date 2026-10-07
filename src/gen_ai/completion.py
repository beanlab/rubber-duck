"""Discord-independent Responses API completion boundary."""

from dataclasses import dataclass
from typing import Any

from openai.types.responses import FunctionToolParam, ResponseInputParam
from pydantic import BaseModel


@dataclass(frozen=True)
class CompletionRequest:
    model: str
    instructions: str
    input: ResponseInputParam
    tools: list[FunctionToolParam]
    tool_choice: Any = "auto"
    output_format: type[BaseModel] | None = None
    reasoning: str | None = None


@dataclass(frozen=True)
class CompletionResult:
    output: list[dict[str, Any]]
    usage: Any = None
    response_id: str | None = None
    provider_model: str | None = None


class ResponsesCompletionAdapter:
    async def complete(self, client: Any, request: CompletionRequest) -> CompletionResult:
        params: dict[str, Any] = {
            "model": request.model,
            "instructions": request.instructions,
            "input": request.input,
            "tools": request.tools,
            "tool_choice": request.tool_choice,
        }
        if request.output_format is not None:
            params["text"] = request.output_format
        if request.reasoning:
            params["reasoning"] = {"effort": request.reasoning}

        response = await client.responses.create(**params)
        return CompletionResult(
            output=[item.model_dump(exclude_none=True) for item in response.output],
            usage=response.usage,
            response_id=getattr(response, "id", None),
            provider_model=getattr(response, "model", None),
        )
