import copy
import inspect
import json
import os
from io import BytesIO
from typing import TypedDict, Protocol

from agents import ToolCallOutputItem
from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError, api_key, OpenAI
from openai.types.responses import Response, ResponseFunctionToolCallParam, ResponseFunctionToolCall, FunctionToolParam
from openai.types.responses.response_input_item import FunctionCallOutput, Message
from quest import step

from ..armory.armory import Armory
from ..armory.tools import register_tool
from ..utils.config_types import DuckContext, AgentMessage, GPTMessage, FileData
from ..utils.logger import duck_logger
from ..utils.protocols import IndicateTyping, SendMessage
from ..utils.validation import is_agent_message

Sendable = str | tuple[str, BytesIO]


class GenAIClient(Protocol):
    async def get_completion(
            self,
            context: DuckContext,
            message_history: list[GPTMessage],
    ) -> AgentMessage: ...


class GenAIException(Exception):
    def __init__(self, exception, web_mention):
        self.exception = exception
        self.web_mention = web_mention
        super().__init__(self.exception.__str__())


class RetryConfig(TypedDict):
    max_retries: int
    delay: int
    backoff: int


class RetryableException(Exception):
    def __init__(self, exception, message):
        self.exception = exception
        self.message = message
        super().__init__(self.exception.__str__())


class RecordMessage(Protocol):
    async def __call__(self, guild_id: int, thread_id: int, user_id: int, role: str, message: str): ...


class RecordUsage(Protocol):
    async def __call__(self, guild_id: int, parent_channel_id: int, thread_id: int, user_id: int, engine: str,
                       input_tokens: int,
                       output_tokens: int, cached_tokens: int, reasoning_tokens: int): ...


def _result_to_agent_message(result):
    last_item = result.new_items[-1]
    if isinstance(last_item, ToolCallOutputItem):
        return AgentMessage(
            agent_name=result.last_agent.name,
            content=last_item.output
        )
    else:
        return AgentMessage(
            agent_name=result.last_agent.name,
            content=result.final_output
        )

class Agent:
    def __init__(self, name: str, description: str, prompt: str, model: str, tools: list[str], armory: Armory, max_iterations: int = 10):
        self._name = name
        self._description = description
        self._prompt = prompt
        self._model = model
        self._tools = tools
        self._tools_json: list[FunctionToolParam] = [armory.get_tool_schema(tool) for tool in tools]
        self._armory = armory
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._max_iterations = max_iterations

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._description

    def add_tool(self, tool: str):
        if tool not in self._tools:
            self._tools.append(tool)
            self._tools_json.append(self._armory.get_tool_schema(tool))

    def _get_completion(self, history: list[GPTMessage | FunctionCallOutput | ResponseFunctionToolCallParam]) -> Response:
        return self._client.responses.create(
            model=self._model,
            instructions=self._prompt,
            input=history,
            tools=self._tools_json
        )

    def _add_function_call_context(self, result: str, call: ResponseFunctionToolCall, message_history: list):
        message_history.append(ResponseFunctionToolCallParam(
            type="function_call",
            id=call.id,
            call_id=call.call_id,
            name=call.name,
            arguments=call.arguments
        ))
        message_history.append(FunctionCallOutput(
            type="function_call_output",
            call_id=call.call_id,
            output=str(result)
        ))

    async def run(self, ctx: DuckContext, message_history: list) -> AgentMessage:
        """
        This method runs a new agent.
        """
        history = message_history
        iterations = 0

        while iterations < self._max_iterations:
            iterations += 1
            response = self._get_completion(history)
            output_item = response.output[0]

            match output_item.type:
                case "function_call":
                    tool_name = output_item.name

                    if tool_name.startswith("run_"):
                        duck_logger.debug(f"Agent {self._name} is calling a handoff tool: {tool_name}")

                    tool_args = json.loads(output_item.arguments)
                    tool = self._armory.get_specific_tool(tool_name)
                    needs_context = self._armory.get_tool_needs_context(tool_name)
                    needs_history = self._armory.get_tool_needs_history(tool_name)

                    call_args = []
                    if needs_context:
                        call_args.append(ctx)
                    if needs_history:
                        call_args.append(history)

                    if inspect.iscoroutinefunction(tool):
                        value = await tool(*call_args, **tool_args)
                    else:
                        value = tool(*call_args, **tool_args)

                    if is_agent_message(value):
                        return value
                    else:
                        self._add_function_call_context(value, output_item, history)

                case "message":
                    return AgentMessage(agent_name=self._name, content=output_item.content[0].text)

        return AgentMessage(
            agent_name=self._name,
            content="I have reached the maximum number of iterations without a valid response."
        )
