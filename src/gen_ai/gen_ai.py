import inspect
import json
import os
from dataclasses import dataclass
from typing import TypedDict, Protocol, Literal, NotRequired, Type, Optional

from openai import OpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.responses import ResponseFunctionToolCallParam, FunctionToolParam, ToolChoiceTypesParam, \
    ToolChoiceFunctionParam
from openai.types.responses.response_input_item import FunctionCallOutput
from pydantic import BaseModel
from quest import step

from ..armory.armory import Armory
from ..utils.config_types import DuckContext, GPTMessage, HistoryType, ReasoningItem
from ..utils.logger import duck_logger


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


@dataclass
class Agent:
    name: str
    prompt: str
    model: str
    tools: list[str]
    tool_settings: ToolChoiceTypes = "auto"
    output_format: Optional[Type[BaseModel]] = None
    reasoning: Optional[str] = None


class Response(TypedDict):
    type: Literal["function_call", "message", "reasoning"]
    name: NotRequired[str]
    arguments: NotRequired[str]
    message: NotRequired[str]
    id: NotRequired[str]
    call_id: NotRequired[str]
    summary: NotRequired[list]


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


def format_reasoning_history_item(id: str, summary: list) -> ReasoningItem:
    return {
        'id': id,
        'type': 'reasoning',
        'summary': summary
    }


class AIClient:
    def __init__(self, armory: Armory, typing, record_message, record_usage: RecordUsage):
        self._armory = armory
        self._typing = typing
        self._record_message = record_message
        self._record_usage = record_usage
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @step
    async def _get_completion(
            self,
            ctx: DuckContext,
            prompt: str,
            history,
            model: str,
            tools: list[FunctionToolParam],
            tool_settings: ToolChoiceTypes,
            output_format: Type[BaseModel] | None,
            reasoning: str | None = None
    ) -> list[Response]:
        async with self._typing(ctx.thread_id):
            params = dict(
                model=model,
                instructions=prompt,
                input=history,
                tools=tools,
                tool_choice=tool_settings
            )

            if output_format:
                params["text_format"] = output_format
            if reasoning:
                params["reasoning"] = {"effort": reasoning}

            response = self._client.responses.parse(**params)

            if response.usage:
                usage = response.usage
                await self._record_usage(ctx.guild_id, ctx.parent_channel_id, ctx.thread_id, ctx.author_id, model,
                                         usage.input_tokens, usage.output_tokens,
                                         usage.input_tokens_details.cached_tokens,
                                         usage.output_tokens_details.reasoning_tokens)

            responses = []
            for item in response.output:
                if item.type == "function_call":
                    responses.append(Response(
                        type="function_call",
                        name=item.name,
                        arguments=item.arguments,
                        call_id=item.call_id,
                        id=item.id
                    ))
                elif item.type == "message":
                    responses.append(Response(type="message",
                                              message=str(
                                                  response.output_parsed) if output_format else response.output_text))

                elif item.type == "reasoning":
                    responses.append(Response(
                        type="reasoning",
                        id=item.id,
                        summary=item.summary
                    ))
                else:
                    raise NotImplementedError(f"Unknown response type")
            return responses

    @step
    async def _run_tool(self, tool, ctx, tool_args):
        try:
            result = tool(ctx, **tool_args)
            if inspect.isawaitable(result):
                result = await result
        except Exception as error:
            result = f"An error occurred while running the tool. Please try again. Error: {str(error)}."
        return result

    @step
    async def run_agent(self, ctx: DuckContext, agent: Agent, query: str):
        tools_json = [self._armory.get_tool_schema(tool_name) for tool_name in agent.tools]
        user_message = GPTMessage(role='user', content=query)
        await self._record_message(ctx.guild_id, ctx.thread_id, ctx.author_id, "message",
                                   json.dumps(user_message))
        history: list[HistoryType] = [GPTMessage(role='user', content=query)]
        try:
            while True:
                outputs = await self._get_completion(ctx, agent.prompt, history, agent.model, tools_json,
                                                     agent.tool_settings, agent.output_format, agent.reasoning)
                for output in outputs:
                    if output['type'] == "reasoning":
                        reasoning_item = format_reasoning_history_item(output['id'], output['summary'])
                        await self._record_message(ctx.guild_id, ctx.thread_id, ctx.author_id, "reasoning",
                                                   str(reasoning_item))
                        history.append(reasoning_item)
                        continue

                    if output['type'] == "function_call":
                        tool_name = output["name"]
                        tool_args = json.loads(output["arguments"])

                        tool = self._armory.get_specific_tool(tool_name)

                        result = await self._run_tool(tool, ctx, tool_args)

                        function_items = format_function_call_history_items(result, output)
                        await self._record_message(ctx.guild_id, ctx.thread_id, ctx.author_id, "function_call",
                                                   str(function_items[0]))
                        await self._record_message(ctx.guild_id, ctx.thread_id, ctx.author_id, "function_call_output",
                                                   str(function_items[1]))
                        history.extend(function_items)

                        continue

                    elif output['type'] == "message":
                        duck_logger.debug("Going back to agent: main_agent")
                        return output['message']

                    else:
                        raise NotImplementedError(f"Unknown response type: {output['type']}")


        except (APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError,
                BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError) as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e
        except Exception as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e

    def build_agent_tool(self, agent, name: str, doc_string: str) -> callable:
        async def agent_runner(ctx: DuckContext, query: str):
            duck_logger.debug(f"Talking to agent: {agent}")
            return await self.run_agent(ctx, agent, query)

        agent_runner.__name__ = name
        agent_runner.__doc__ = doc_string
        return agent_runner
