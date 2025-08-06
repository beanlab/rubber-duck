import inspect
import json
import os
from io import BytesIO
from typing import TypedDict, Protocol, Literal, NotRequired

from openai import OpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.responses import ResponseFunctionToolCallParam, FunctionToolParam, ToolChoiceTypesParam, \
    ToolChoiceFunctionParam
from openai.types.responses.response_input_item import FunctionCallOutput
from pydantic import BaseModel
from quest import step

from ..armory.armory import Armory
from ..utils.config_types import DuckContext, GPTMessage, HistoryType

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
    def __init__(self, name: str, description: str | None, prompt: str, model: str, tools: list[str],
                 tool_settings: ToolChoiceTypes = "auto", goal: str | None = None):
        self.name = name
        self.description = description
        self.prompt = prompt
        self.model = model
        self.tools = tools
        self.tool_settings = tool_settings
        self.goal = goal


class Response(TypedDict):
    type: Literal["function_call", "message"]
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

def stringify_conversation_history(history: list[HistoryType]) -> str:
    return "\n".join(
        json.dumps(dict(entry), ensure_ascii=False) for entry in history
    )

class GoalCheckResult(BaseModel):
    accomplished: bool
    description: str

class AIClient:
    def __init__(self, armory: Armory):
        self._armory = armory
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


    async def _check_against_goal(self, goal: str, history: list[HistoryType]) -> GoalCheckResult:
        response = self._client.responses.parse(
            model="gpt-4.1-mini",
            instructions=f"You are a goal-checking professional. Your task is to determine if a conversation history \
            meets a required goal if it does meet the goal you return true and your description is how the goal was met. \
            If it does not meet the goal you return false and your description is how it did not meet the goal. In either case \
            your description should be concise and to the point.",
            input=f"This is the goal: {goal}\n\nThis is the conversation history: {stringify_conversation_history(history)}\n",
            text_format=GoalCheckResult
        )
        return response

    @step
    async def _get_completion(self, prompt: str, history, model: str, tools: list[FunctionToolParam],
                              tool_settings: ToolChoiceTypes) -> Response:
        response = self._client.responses.create(
            model=model,
            instructions=prompt,
            input=history,
            tools=tools,
            tool_choice=tool_settings
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
    async def run_agent(self, ctx: DuckContext, agent: Agent, query: str):
        tools_json = [self._armory.get_tool_schema(tool_name) for tool_name in agent.tools]
        history: list[HistoryType] = [GPTMessage(role='user', content=query)]
        try:
            while True:
                output = await self._get_completion(agent.prompt, history, agent.model, tools_json, agent.tool_settings)
                if output['type'] == "function_call":
                    tool_name = output["name"]
                    tool_args = json.loads(output["arguments"])

                    tool = self._armory.get_specific_tool(tool_name)

                    needs_context = self._armory.get_tool_needs_context(tool_name)

                    result = tool(ctx, **tool_args) if needs_context else tool(**tool_args)

                    if inspect.isawaitable(result):
                        result = await result

                    history.extend(format_function_call_history_items(result, output))

                    if agent.goal:
                        check = await self._check_against_goal(agent.goal, history)
                        check = check.output_parsed
                        if check.accomplished is False:
                            history.append(GPTMessage(role='developer', content=f"Goal not accomplished for the following reason: {check.description}"))
                        elif check.accomplished is True:
                            return (f"The user has finished using the {agent.name} tool, and has indicated they would like to talk about another subject. \""
                                    f"use the talk_to_user tool to determine how they would like to continue the conversation.")
                        continue

                    continue

                elif output['type'] == "message":
                    message = f"Use the talk_to_user tool to respond with this message {output['message']}"
                    history.append(GPTMessage(role='developer', content=message))
                    continue

        except (APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError,
                BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError) as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e
        except Exception as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e
