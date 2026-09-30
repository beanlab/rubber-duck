import inspect
import json
from dataclasses import dataclass, field
from typing import TypedDict, Callable, Literal, Optional, Type

from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, BadRequestError, \
    AuthenticationError, ConflictError, NotFoundError, RateLimitError, AsyncOpenAI
from openai.lib._parsing._responses import type_to_text_format_param
from openai.types.responses import ToolChoiceTypesParam, ToolChoiceFunctionParam, FunctionToolParam, Response, \
    ResponseInputItemParam
from openai.types.responses.response_input_item import FunctionCallOutput
from pydantic import BaseModel, ValidationError
from quest import step

from ..armory.armory import Armory
from ..utils.config_types import RetryProtocol
from ..utils.retry import retry_async, retry_delay_seconds, is_retryable_discord_server_error


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
    prompt: Optional[str] = None
    reasoning: Optional[str] = None
    tools: Optional[ToolBox] = None
    tool_settings: ToolChoiceTypes = "auto"
    output_format: Optional[Type[BaseModel]] = None


class AIResponse(TypedDict):
    outputs: list[HistoryType]
    usage: Usage | None
    result: str | BaseModel | None


def format_function_call_history_items(result: str, call_id) -> FunctionCallOutput:
    return FunctionCallOutput(
        type="function_call_output",
        call_id=call_id,
        output=str(result)
    ).model_dump(exclude_none=True)


async def _ignore_retry(_seconds: int):
    return None


class ResponsesAPI:
    def __init__(
            self,
            armory: Armory,
            retry_protocol: RetryProtocol,
            client: AsyncOpenAI | None = None,
    ):
        self._armory = armory
        self._retry_protocol = retry_protocol
        self._client = client or AsyncOpenAI()

    @staticmethod
    def _is_retryable_server_overload(error: InternalServerError) -> bool:
        if getattr(error, "status_code", None) != 503:
            return False
        body = getattr(error, "body", None)
        if not isinstance(body, dict):
            return True
        payload = body.get("error")
        if not isinstance(payload, dict):
            return True
        return payload.get("code") == "server_is_overloaded"

    def _should_retry(self, error: Exception) -> bool:
        if isinstance(error, InternalServerError):
            return self._is_retryable_server_overload(error)
        return is_retryable_discord_server_error(error)

    def _retry_delay_seconds(self, attempt: int) -> int:
        return retry_delay_seconds(self._retry_protocol, attempt)

    @staticmethod
    def _validate_output(
            agent_name: str,
            message: str | None,
            output_format: Type[BaseModel] | None,
    ) -> str | BaseModel | None:
        if output_format is None:
            return message

        try:
            return output_format.model_validate_json(message)
        except ValidationError as error:
            raise GenAIException(
                error,
                f"{agent_name} returned invalid structured output, expected {output_format.__name__}",
            ) from error

    @staticmethod
    def _message_text(outputs: list[HistoryType]) -> str | None:
        for output in outputs:
            if output.get("type") != "message":
                continue
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text")
        return None

    @staticmethod
    def _add_usage(total: Usage | None, current: Usage | None) -> Usage | None:
        if current is None:
            return total
        if total is None:
            return current.copy()
        for key in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens"):
            total[key] += current[key]
        return total

    @staticmethod
    def _tool_value(result):
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], bool):
            return result[0]
        return result

    @step
    async def run_agent_turn(
            self, agent: Agent, history: list[HistoryType],
            notify_retry: Callable = _ignore_retry
    ) -> AIResponse:
        try:
            turn_outputs: list[HistoryType] = []
            total_usage = None

            while True:
                outputs, usage = await self._get_completion(
                    agent.model, agent.prompt, agent.reasoning,
                    agent.tools.get_tool_schemas(),
                    agent.tool_settings,
                    agent.output_format,
                    history + turn_outputs,
                    notify_retry=notify_retry,
                )
                total_usage = self._add_usage(total_usage, usage)
                turn_outputs += outputs

                tool_results = []
                for output in outputs:
                    if output["type"] != "function_call":
                        continue

                    tool_name = output["name"]
                    tool_args = json.loads(output["arguments"])
                    tool = agent.tools.get_tool(tool_name)
                    result = await self._run_tool(tool, tool_args)

                    function_item = format_function_call_history_items(
                        self._tool_value(result),
                        output["call_id"],
                    )
                    tool_results.append(function_item)

                turn_outputs += tool_results

                message = self._message_text(outputs)
                if message is not None:
                    return AIResponse(
                        outputs=turn_outputs,
                        usage=total_usage,
                        result=self._validate_output(agent.name, message, agent.output_format),
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

    @step
    async def _get_completion(
            self,
            model: str,
            prompt: str | None,
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
            tool_choice=tool_settings,
        )
        if prompt:
            params["instructions"] = prompt

        if output_format:
            params["text"] = type_to_text_format_param(output_format)

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
            input_token_details = getattr(response.usage, "input_token_details", None)
            output_token_details = getattr(response.usage, "output_tokens_details", None)
            usage = Usage(
                model=model,
                reasoning=reasoning,
                input_tokens=response.usage.input_tokens,
                cached_tokens=getattr(input_token_details, "cached_tokens", 0) or 0,
                output_tokens=response.usage.output_tokens,
                reasoning_tokens=getattr(output_token_details, "reasoning_tokens", 0) or 0,
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
