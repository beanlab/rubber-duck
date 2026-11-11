"""Discord-independent completion boundary for prompt evaluations."""

from dataclasses import dataclass
from typing import Protocol, TypeAlias

from openai.types.responses import FunctionToolParam, Response, ResponseInputParam
from openai.types.responses.response_create_params import (
    ResponseCreateParamsNonStreaming,
    ToolChoice,
)
from openai.types.responses.response_format_text_json_schema_config_param import (
    ResponseFormatTextJSONSchemaConfigParam,
)
from openai.types.responses.response_text_config_param import ResponseTextConfigParam
from openai.types.responses.response_usage import ResponseUsage
from openai.types.shared_params.reasoning_effort import ReasoningEffort
from pydantic import BaseModel, TypeAdapter
from typing_extensions import Unpack


class ResponsesCompletionAPI(Protocol):
    async def create(
        self,
        **params: Unpack[ResponseCreateParamsNonStreaming],
    ) -> Response: ...


class CompletionClient(Protocol):
    @property
    def responses(self) -> ResponsesCompletionAPI: ...


_OUTPUT_ITEM = TypeAdapter(dict[str, object])
_OUTPUT_SCHEMA = TypeAdapter(dict[str, object])
StructuredOutputFormat: TypeAlias = type[BaseModel] | ResponseTextConfigParam


@dataclass(frozen=True)
class CompletionRequest:
    model: str
    instructions: str
    input: ResponseInputParam
    tools: list[FunctionToolParam]
    tool_choice: ToolChoice = "auto"
    output_format: StructuredOutputFormat | None = None
    reasoning: ReasoningEffort = None


@dataclass(frozen=True)
class CompletionResult:
    output: list[dict[str, object]]
    usage: ResponseUsage | None = None
    response_id: str | None = None
    provider_model: str | None = None


class ResponsesCompletionAdapter:
    async def complete(
        self,
        client: CompletionClient,
        request: CompletionRequest,
    ) -> CompletionResult:
        params: ResponseCreateParamsNonStreaming = {
            "model": request.model,
            "instructions": request.instructions,
            "input": request.input,
            "tools": request.tools,
            "tool_choice": request.tool_choice,
        }
        if request.output_format is not None:
            params["text"] = _response_text_config(request.output_format)
        if request.reasoning:
            params["reasoning"] = {"effort": request.reasoning}

        response = await client.responses.create(**params)
        return CompletionResult(
            output=[
                _OUTPUT_ITEM.validate_python(item.model_dump(exclude_none=True))
                for item in response.output
            ],
            usage=response.usage,
            response_id=response.id,
            provider_model=response.model,
        )


def _response_text_config(
    output_format: StructuredOutputFormat,
) -> ResponseTextConfigParam:
    if isinstance(output_format, type) and issubclass(output_format, BaseModel):
        schema: ResponseFormatTextJSONSchemaConfigParam = {
            "type": "json_schema",
            "name": output_format.__name__,
            "schema": _OUTPUT_SCHEMA.validate_python(
                output_format.model_json_schema()
            ),
            "strict": True,
        }
        return {"format": schema}
    return output_format
