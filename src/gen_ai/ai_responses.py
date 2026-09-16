import inspect
import json
from dataclasses import dataclass, field
from typing import TypedDict, Callable, Literal, Optional, Type

from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, BadRequestError, \
    AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.responses import ToolChoiceTypesParam, ToolChoiceFunctionParam, FunctionToolParam, Response, \
    ResponseInputItemParam
from openai.types.responses.response_input_item import FunctionCallOutput
from pydantic import BaseModel
from quest import step

from ..armory.armory import Armory
from ..utils.retry import retry_async


class GenAIException(Exception):
    def __init__(self, exception, web_mention):
        self.exception = exception
        self.web_mention = web_mention
        super().__init__(self.exception.__str__())


ToolChoiceTypes = Literal["none", "auto", "required"] | ToolChoiceTypesParam | ToolChoiceFunctionParam

HistoryType = ResponseInputItemParam


class Usage(TypedDict):
    model: str
    reasoning: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    reasoning_tokens: int


@dataclass
class Agent:
    name: str
    model: str
    armory: Armory
    prompt: Optional[str] = None
    tools: dict[str, Callable] = field(default_factory=dict)
    reasoning: Optional[str] = None
    tool_settings: ToolChoiceTypes = "auto"
    output_format: Optional[Type[BaseModel]] = None


class AIResponse(TypedDict):
    outputs: list[HistoryType]
    usage: Usage


def format_function_call_history_items(result: str, call_id) -> FunctionCallOutput:
    return FunctionCallOutput(
        type="function_call_output",
        call_id=call_id,
        output=str(result)
    ).model_dump(exclude_none=True)


class ResponsesAPI:
    @step
    async def run_agent_turn(
            self, agent: Agent, history: list[HistoryType],
            notify_retry: Callable = lambda seconds: None
    ) -> AIResponse:
        try:
            outputs, usage = await self._get_completion(
                agent.model, agent.reasoning,
                agent.armory.get_tool_schemas(),
                agent.armory.get_tool_settings(),
                agent.output_format,
                history,
                notify_retry=notify_retry
            )

            tool_results = []
            for output in outputs:
                if output['type'] == "function_call":
                    tool_name = output["name"]
                    tool_args = json.loads(output["arguments"])

                    tool = agent.armory.get_specific_tool(tool_name)
                    result = await self._run_tool(tool, tool_args)

                    function_item = format_function_call_history_items(result, output['call_id'])
                    tool_results.append(function_item)

                    # await self._record_message(
                    #     ctx.guild_id, ctx.thread_id, ctx.author_id,
                    #     "function_call_output", str(function_item)
                    # )
            outputs += tool_results
            
            return AIResponse(
                outputs=outputs,
                usage=usage
            )

        except (
                APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError,
                BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
        ) as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e

        except GenAIException:
            raise

        except Exception as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e

    async def _get_completion(
            self,
            model: str,
            reasoning: str | None,
            tools: list[FunctionToolParam],
            tool_settings: ToolChoiceTypes,
            output_format: Type[BaseModel] | None,
            history: list[HistoryType],
            notify_retry: Callable
    ) -> tuple[list, Usage]:

        params = dict(
            model=model,
            input=history,
            tools=tools,
            tool_choice=tool_settings
        )

        if output_format:
            # noinspection PyTypeChecker
            params["text"] = output_format

        if reasoning:
            # noinspection PyTypeChecker
            params["reasoning"] = {"effort": reasoning}

        async def create_completion():
            return await self._client.responses.create(**params)

        async def on_retry(_error: Exception, attempt: int, _delay_seconds: int):
            await notify_retry(self._retry_delay_seconds(attempt))

        response: Response = await retry_async(
            create_completion,
            self._retry_protocol,
            self._should_retry,
            on_retry
        )

        usage = None
        if response.usage:
            usage = Usage(
                model=model,
                reasoning=reasoning,
                input_tokens=response.usage.input_tokens,
                cached_tokens=response.usage.input_token_details.cached_tokens,
                output_tokens=response.usage.output_tokens,
                reasoning_tokens=response.usage.output_tokens_details.reasoning_tokens
            )

        return [
            resp.model_dump(exclude_none=True)
            for resp in response.output
        ], usage

    @step
    async def _run_tool(self, tool, tool_args):
        try:
            result = tool(**tool_args)
            if inspect.isawaitable(result):
                result = await result

        except Exception as error:
            if isinstance(error, GenAIException):
                raise
            result = f"An error occurred while running the tool. Please try again. Error: {str(error)}.", False

        return result
