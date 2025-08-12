import inspect
import json
import os
from io import BytesIO
from typing import TypedDict, Protocol, Literal, NotRequired, Type

from openai import OpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.responses import ResponseFunctionToolCallParam, FunctionToolParam, ToolChoiceTypesParam, \
    ToolChoiceFunctionParam
from openai.types.responses.response_input_item import FunctionCallOutput
from pydantic import BaseModel
from quest import step

from ..armory.armory import Armory
from ..utils.config_types import DuckContext, GPTMessage, HistoryType
from ..utils.logger import duck_logger

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


ToolChoiceTypes = Literal["none", "auto", "required"] | ToolChoiceTypesParam | ToolChoiceFunctionParam


class Agent:
    def __init__(self, name: str, prompt: str, model: str, tools: list[str], usage: str,
                 tool_settings: ToolChoiceTypes = "auto", output_format: Type[BaseModel] | None = None):
        self.name = name
        self.prompt = prompt
        self.model = model
        self.tools = tools
        self.usage = usage
        self.tool_settings = tool_settings
        self.output_format = output_format


class Response(TypedDict):
    type: Literal["function_call", "message"]
    structured_output: NotRequired[bool]
    name: NotRequired[str]
    arguments: NotRequired[str]
    message: NotRequired[str]
    id: NotRequired[str]
    call_id: NotRequired[str]


def format_function_call_history_items(result: str, call: Response):
    return [
        ResponseFunctionToolCallParam(
            type="function_call",
            id=call['id'],
            call_id=call['call_id'],
            name=call['name'],
            arguments=call['arguments']
        ),
        FunctionCallOutput(
            type="function_call_output",
            call_id=call['call_id'],
            output=str(result)
        )
    ]


class AIClient:
    def __init__(self, armory: Armory):
        self._armory = armory
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @step
    async def _get_completion(
            self,
            prompt: str,
            history,
            model: str,
            tools: list[FunctionToolParam],
            tool_settings: ToolChoiceTypes,
            output_format: Type[BaseModel] | None
    ) -> Response:
        params = dict(
            model=model,
            instructions=prompt,
            input=history,
            tools=tools,
            tool_choice=tool_settings
        )

        if output_format:
            params["text_format"] = output_format

        response = self._client.responses.parse(**params)

        output_item = response.output[0]

        if output_item.type == "function_call":
            return Response(
                type="function_call",
                name=output_item.name,
                arguments=output_item.arguments,
                call_id=output_item.call_id,
                id=output_item.id
            )
        return Response(type="message",
                        message=str(response.output_parsed) if output_format else output_item.content[0].text,
                        structured_output=bool(output_format))

    @step
    async def run_agent(self, ctx: DuckContext, agent: Agent, query: str):
        tools_json = [self._armory.get_tool_schema(tool_name) for tool_name in agent.tools]
        history: list[HistoryType] = [GPTMessage(role='user', content=query)]
        try:
            while True:
                output = await self._get_completion(agent.prompt, history, agent.model, tools_json,
                                                    agent.tool_settings, agent.output_format)
                if output['type'] == "function_call":
                    tool_name = output["name"]
                    tool_args = json.loads(output["arguments"])

                    tool = self._armory.get_specific_tool(tool_name)

                    result = tool(ctx, **tool_args)

                    if inspect.isawaitable(result):
                        result = await result

                    history.extend(format_function_call_history_items(result, output))

                    continue

                elif output['type'] == "message":
                    if output.get('structured_output'):
                        tool = self._armory.get_specific_tool("send_file")
                        await tool(ctx, output['message'])
                        return output['message']
                    else:
                        return output['message']

                else:
                    raise NotImplementedError(f"Unknown response type: {output['type']}")


        except (APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError,
                BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError) as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e
        except Exception as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e

    def build_agent_tool(self, agent: Agent, tool_name: str, tool_description: str) -> callable:
        async def agent_runner(ctx: DuckContext, query: str):
            duck_logger.debug(f"Talking to agent: {agent.name}")
            return await self.run_agent(ctx, agent, query)
        agent_runner.__name__ = tool_name
        agent_runner.__doc__ = f"Description: {tool_description}\n\nUsage: {agent.usage}"
        return agent_runner
