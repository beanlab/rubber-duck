import asyncio
import logging
import os
from io import BytesIO
from typing import TypedDict, Protocol

from agents import Agent, FunctionTool
from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError, OpenAI
from openai.types.responses import Response
from quest import step

from ..armory.armory import Armory
from ..utils.config_types import DuckContext, AgentMessage, GPTMessage
from ..utils.logger import duck_logger
from ..utils.protocols import IndicateTyping, SendMessage

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


async def _run_with_exception_handling(coroutine):
    try:
        return await coroutine
    except (
            APITimeoutError, InternalServerError,
            UnprocessableEntityError) as ex:
        raise RetryableException(ex, 'I\'m having trouble connecting to the OpenAI servers, '
                                     'please open up a separate conversation and try again') from ex
    except (APIConnectionError, BadRequestError,
            AuthenticationError, ConflictError, NotFoundError,
            RateLimitError) as ex:
        duck_logger.exception(f"AgentClient get_completion Exception: {ex}")
        raise GenAIException(ex, "Visit https://platform.openai.com/docs/guides/error-codes/api-errors "
                                 "for more details on how to resolve this error") from ex


class AgentClient:
    def __init__(
            self,
            agent: Agent,
            typing: IndicateTyping,
            armory: Armory
    ):
        self._initial_agent = agent
        self._typing = typing
        self._armory = armory
        self._agent_handoff_tools = {}
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list,
    ) -> AgentMessage:
        return await _run_with_exception_handling(self._get_completion(
            context,
            message_history
        ))

    async def _get_completion(
            self,
            context: DuckContext,
            message_history: list
    ) -> AgentMessage:

        agent = self._initial_agent
        if agent.name not in self._agent_handoff_tools:
            tools = self.create_handoff_tools(agent, message_history, context)
            self._agent_handoff_tools[agent.name] = tools
            agent.tools += tools

        async with self._typing(context.thread_id):
            result = await self.run(
                agent,
                message_history,
                context=context
            )
            return result

    def _to_tool(self, tool: FunctionTool) -> dict:
        return {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.params_json_schema,
            "strict": True
        }

    async def get_agent_completion(self, agent: Agent, history: list) -> Response:
        response = self._client.responses.create(
            model=agent.model,
            input=history,
            tools=[self._to_tool(tool) for tool in agent.tools]
        )
        return response

    def create_handoff_tools(self, agent: Agent, message_history, context) -> list[FunctionTool]:
        handoff_tools = []
        for handoff_agent in agent.handoffs:
            if handoff_agent:
                tool_name = f"transfer_to_{handoff_agent.name.replace(' ', '_').lower()}"

                def create_handoff_closure(target_agent):
                    async def handoff_tool(message: str):
                        await self.run(target_agent, message_history, context)
                    handoff_tool.__name__ = tool_name
                    return handoff_tool

                tool = self._armory.add_tool(create_handoff_closure(handoff_agent))
                tool.description = handoff_agent.handoff_description or f"Transfer to {handoff_agent.name}"
                handoff_tools.append(tool)

        return handoff_tools

    async def run(self, agent: Agent, message_history: list, context: DuckContext) -> AgentMessage:
        current_agent = agent
        while True:
            recent_messages = message_history[-10:]
            history = [{"role": "system", "content": current_agent.instructions}] + recent_messages
            response = await self.get_agent_completion(current_agent, history)
            output_item = response.output[0]
            match output_item.type:
                case "message":
                    text_content = output_item.content[0].text
                    return AgentMessage(agent_name=current_agent.name, content=text_content)

                case "function_call":
                    tool_name = output_item.name
                    tool_args = output_item.arguments

                    tool = self._armory.get_specific_tool(tool_name)

                    result = await tool.on_invoke_tool(context, tool_args)

                    # Check if this was a handoff tool
                    if tool_name.startswith("transfer_to_") and isinstance(result, Agent):
                        current_agent = result
                        # Ensure handoff tools are created for the new agent
                        if current_agent.name not in self._agent_handoff_tools:
                            tools = self.create_handoff_tools(current_agent)
                            self._agent_handoff_tools[current_agent.name] = tools
                            current_agent.tools += tools
                        result = f"Successfully transferred to {current_agent.name}"

                    message_history.append(output_item)

                    message_history.append({
                        "type": "function_call_output",
                        "call_id": output_item.call_id,
                        "output": str(result)
                    })

                    continue


class RetryableGenAI:
    def __init__(self,
                 genai: GenAIClient,
                 send_message: SendMessage,
                 retry_config: RetryConfig
                 ):
        self._send_message = step(send_message)
        self._retry_config = retry_config
        self._genai = genai

    async def get_completion(
            self,
            context: DuckContext,
            message_history: list[GPTMessage],
    ):
        max_retries = self._retry_config['max_retries']
        delay = self._retry_config['delay']
        backoff = self._retry_config['backoff']
        retries = 0
        while True:
            try:
                return await self._genai.get_completion(
                    context, message_history
                )

            except RetryableException as ex:
                if retries == 0:
                    await self._send_message(context.thread_id, 'Trying to contact servers...')
                retries += 1
                if retries > max_retries:
                    raise GenAIException(ex, 'Retry limit exceeded')

                logging.warning(
                    f"Retrying due to {ex}, attempt {retries}/{max_retries}. Waiting {delay} seconds.")
                await asyncio.sleep(delay)
                delay *= backoff