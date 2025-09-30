import inspect
import json
import os
from dataclasses import dataclass
from typing import Protocol, Literal, Type, Optional, Callable

from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError, AsyncOpenAI
from openai.types.responses import FunctionToolParam, ToolChoiceTypesParam, \
    ToolChoiceFunctionParam, Response, EasyInputMessage
from pydantic import BaseModel
from quest import step

from ..armory.armory import Armory
from ..armory.talk_tool import ConversationComplete
from ..utils.config_types import DuckContext, HistoryType
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


class FunctionCallOutput(BaseModel):
    call_id: str
    output: str
    type: Literal["function_call_output"]
    id: Optional[str] = None
    status: Optional[Literal["in_progress", "completed", "incomplete"]] = None


def format_function_call_history_items(result: str, call: Response) -> FunctionCallOutput:
    return FunctionCallOutput(
        type="function_call_output",
        call_id=call['call_id'],
        output=str(result)
    ).model_dump(exclude_none=True)


class AIClient:
    def __init__(self, armory: Armory, typing, record_message, record_usage: RecordUsage):
        self._armory = armory
        self._typing = typing
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @step
    async def _get_completion(
            self,
            ctx: DuckContext,
            prompt: str,
            local_history,
            context,
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
                input=(context + local_history),
                tools=tools,
                tool_choice=tool_settings
            )

            if output_format:
                params["text"] = output_format

            if reasoning:
                params["reasoning"] = {"effort": reasoning}

            response = await self._client.responses.create(**params)

            if response.usage:
                usage = response.usage
                await self._record_usage(ctx.guild_id, ctx.parent_channel_id, ctx.thread_id, ctx.author_id, model,
                                         usage.input_tokens, usage.output_tokens,
                                         usage.input_tokens_details.cached_tokens,
                                         usage.output_tokens_details.reasoning_tokens)

            return [
                resp.model_dump(exclude_none=True)
                for resp in response.output
            ]

    @step
    async def _run_tool(self, tool, ctx, tool_args) -> tuple[str | None, bool]:
        try:
            result = tool(ctx, **tool_args)
            if inspect.isawaitable(result):
                result = await result
        except Exception as error:
            if isinstance(error, GenAIException):
                raise error
            result = f"An error occurred while running the tool. Please try again. Error: {str(error)}.", False
        return result

    async def run_agent(self, ctx: DuckContext, agent: Agent, query: str | None) -> str | None:
        initial_history = []

        if query is not None:
            await self._record_message(ctx.guild_id, ctx.thread_id, ctx.author_id, "message",
                                       json.dumps(query))
            initial_history.append(EasyInputMessage(role='user', content=query, type='message').model_dump())

        message, history, _ = await self._run_agent(ctx, agent, initial_history)
        return message

    async def run_conversation(self, ctx: DuckContext, agent: Agent, get_user_message, send_user_message) -> list[
        HistoryType]:
        history = []
        while True:
            try:
                user_message = await get_user_message(ctx)

            except TimeoutError:
                break

            await self._record_message(ctx.guild_id, ctx.thread_id, ctx.author_id, "message",
                                       json.dumps(user_message))

            history.append(EasyInputMessage(role='user', content=user_message, type='message').model_dump())
            agent_response, agent_history, conversation_complete = await self._run_agent(ctx, agent, history)

            if agent_response:
                await send_user_message(ctx, agent_response)

            history.extend(agent_history)

            if conversation_complete:
                break

        return history

    @step
    async def _run_agent(self,
                         ctx: DuckContext, agent: Agent, context: list[HistoryType]
                         ) -> tuple[str | None, list[HistoryType], bool]:
        tools_json = [self._armory.get_tool_schema(tool_name) for tool_name in agent.tools]
        history: list[HistoryType] = []
        try:
            while True:
                outputs = await self._get_completion(
                    ctx, agent.prompt, history, context,
                    agent.model, tools_json, agent.tool_settings,
                    agent.output_format, agent.reasoning
                )

                history += outputs
                for output in outputs:
                    # TODO - handle all possible outputs gracefully
                    if 'role' not in output:
                        continue
                    await self._record_message(
                        ctx.guild_id, ctx.thread_id, ctx.author_id,
                        output['role'], str(output['content'])  # <-- what should output store for each type of output
                    )

                for output in outputs:
                    if output['type'] == "function_call":
                        tool_name = output["name"]
                        tool_args = json.loads(output["arguments"])

                        tool = self._armory.get_specific_tool(tool_name)

                        try:
                            result = await self._run_tool(tool, ctx, tool_args)
                            function_item = format_function_call_history_items(result[0], output)
                            await self._record_message(
                                ctx.guild_id, ctx.thread_id, ctx.author_id,
                                "function_call_output", str(function_item)
                            )

                            history.append(function_item)

                            if result[1]:
                                return None, history, False
                            continue

                        except ConversationComplete:
                            return None, history, True

                    elif output['type'] == "message":
                        message = output['content'][0]['text']  # TODO - should we be more intelligent here?
                        return message, history, False

                    elif output['type'] == 'reasoning':
                        pass  # FUTURE - could do something clever with this

                    else:
                        raise NotImplementedError(f"Unknown response type: {output['type']}")

        except (APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError,
                BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError) as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e
        except Exception as e:
            raise GenAIException(e, f"An error occurred while processing query for {agent.name}") from e

    def build_agent_tool(self, agent, name: str, doc_string: str) -> Callable:
        async def agent_runner(ctx: DuckContext, query: str):
            duck_logger.debug(f"Talking to agent: {agent}")
            return await self.run_agent(ctx, agent, query)

        agent_runner.__name__ = name
        agent_runner.__doc__ = doc_string
        return agent_runner

    def _check_for_history(self, my_func: Callable):
        sig = inspect.signature(my_func)
        params = sig.parameters
        if "history" in params:
            return True
        return False
