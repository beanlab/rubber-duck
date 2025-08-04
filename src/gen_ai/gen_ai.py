import inspect
import json
import os
from io import BytesIO
from typing import TypedDict, Protocol, Literal, Union, NotRequired

from openai import OpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.responses import  ResponseFunctionToolCallParam, ResponseFunctionToolCall, FunctionToolParam
from openai.types.responses.response_input_item import FunctionCallOutput
from quest import step

from ..armory.armory import Armory
from ..armory.tools import needs_context
from ..utils.config_types import DuckContext, GPTMessage, HistoryType
from ..utils.validation import is_gpt_message

Sendable = str | tuple[str, BytesIO]

class GenAIException(Exception):
    def __init__(self, exception, web_mention):
        self.exception = exception
        self.web_mention = web_mention
        super().__init__(self.exception.__str__())

class RecordMessage(Protocol):
    async def __call__(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str): ...


class RecordUsage(Protocol):
    async def __call__(self, guild_id: int, parent_channel_id: int, thread_id: int, user_id: int, engine: str,
                       input_tokens: int,
                       output_tokens: int, cached_tokens: int, reasoning_tokens: int): ...


class Agent:
    def __init__(self, name: str, description: str, prompt: str, model: str, tools: list[str]):
        self.name = name
        self.description = description
        self.prompt = prompt
        self.model = model
        self.tools = tools

        self.tools.append("talk_to_user")

class Response(TypedDict):
    type: Literal["function_call", "message"]
    name: NotRequired[str]
    arguments: NotRequired[str]
    message: NotRequired[str]
    id: NotRequired[str]
    call_id: NotRequired[str]

class AIClient:
    def __init__(self, armory: Armory):
        self._armory = armory
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _add_function_call_context(self, result: str, call: Response, message_history: list):
        message_history.append(ResponseFunctionToolCallParam(
            type="function_call",
            id=call['id'],
            call_id=call['call_id'],
            name=call['name'],
            arguments=call['arguments']
        ))
        message_history.append(FunctionCallOutput(
            type="function_call_output",
            call_id=call['call_id'],
            output=str(result)
        ))

    @step
    async def _get_completion(self, prompt: str, history, model: str, tools: list[FunctionToolParam]) -> Response:
        response = self._client.responses.create(
            model=model,
            instructions=prompt,
            input=history,
            tools=tools
        )
        output_item = response.output[0]
        if output_item.type == "function_call":
            return Response(
                type="function_call",
                name=output_item.name,
                arguments=output_item.arguments,
                call_id=output_item.call_id,
                id=output_item.id
            )
        else:
            return Response(
                type="message",
                message=output_item.content[0].text
            )

    @step
    async def run_agent(self, ctx: DuckContext, history: list[HistoryType],  agent: Agent):
        tools_json = [self._armory.get_tool_schema(tool_name) for tool_name in agent.tools]
        try:
            while True:
                output = await self._get_completion(agent.prompt, history, agent.model, tools_json)
                if output['type'] == "function_call":
                    tool_name = output["name"]
                    tool_args = json.loads(output["arguments"])

                    tool = self._armory.get_specific_tool(tool_name)

                    need_context = self._armory.get_tool_needs_context(tool_name)
                    need_history = self._armory.get_tool_needs_history(tool_name)

                    if need_context:
                        if need_history:
                            self._add_function_call_context(f"{tool_name}", output, history)
                            result = tool(ctx, history, **tool_args)
                        else:
                            result = tool(ctx, **tool_args)
                    else:
                        result = tool(**tool_args)

                    if inspect.isawaitable(result):
                        result = await result

                    if is_gpt_message(result):
                        history.append(result)
                        continue
                    else:
                        self._add_function_call_context(result, output, history)
                        continue

                elif output['type'] == "message":
                    return GPTMessage(role="assistant", content=output["message"])

        except (APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError,
                BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError) as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e
        except Exception as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e