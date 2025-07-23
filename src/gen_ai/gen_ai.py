import asyncio
import logging
import os
from io import BytesIO
from typing import TypedDict, Protocol, Optional, Literal

from agents import Agent, Runner, ToolCallOutputItem, FunctionTool
from openai import APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError, OpenAI
from openai.types.responses import Response, ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput
from quest import step

from ..armory.armory import Armory
from ..utils.config_types import DuckContext, AgentMessage, GPTMessage, FileData
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


def _result_to_agent_message(result):
    last_item = result.new_items[-1]
    if isinstance(last_item, ToolCallOutputItem):
        return AgentMessage(
            agent_name=result.last_agent.name,
            file=FileData(filename=last_item.output[0], bytes=last_item.output[1])
        )
    else:
        return AgentMessage(
            agent_name=result.last_agent.name,
            content=result.final_output
        )


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

class Message(TypedDict):
    role: Literal['system', 'developer', 'user', 'assistant']
    content: str



class Context:
    def __init__(self):
        self._items: list[Message | ResponseFunctionToolCallParam | FunctionCallOutput] = []

    def update(self, new_item: Message | ResponseFunctionToolCallParam | FunctionCallOutput):
        self._items.append(new_item)

    def get_items(self) -> list[Message | ResponseFunctionToolCallParam | FunctionCallOutput]:
        return self._items

    def get_string_items(self) -> str:
        lines = []
        for item in self._items:
            if isinstance(item, dict):
                if item.get("role"):
                    lines.append(f"{item['role'].upper()}: {item['content']}")
                elif item.get("type") == "function_call":
                    lines.append(f"FUNCTION CALL [{item['name']}] with args: {item['arguments']}")
                elif item.get("type") == "function_output":
                    lines.append(f"FUNCTION OUTPUT for call {item['call_id']}: {item['output']}")
                else:
                    lines.append(str(item))
            else:
                lines.append(str(item))
        return "\n".join(lines)

    def __iter__(self):
        return iter(self._items)

class ConversationSession:
    def __init__(self):
        self.agent_contexts: dict[str, Context] = {}
        self.current_agent_name: Optional[str] = None
        self.conversation_active: bool = True

    def get_context(self, agent_name: str) -> Context:
        if agent_name not in self.agent_contexts:
            self.agent_contexts[agent_name] = Context()
        return self.agent_contexts[agent_name]

    def reset(self):
        self.agent_contexts.clear()
        self.current_agent_name = None
        self.conversation_active = True


class AgentCoordinator:
    def __init__(self):
        self.agents = {}

    def register_agent(self, agent: Agent):
        self.agents[agent.get_agent_name()] = agent

    def setup_handoffs(self, tool_registry: ToolRegistry):
        for agent_name, agent in self.agents.items():
            handoff_tools = []
            for target_agent_name in agent.handoff_agent_names:
                if target_agent_name in self.agents:
                    target_agent = self.agents[target_agent_name]
                    handoff_tool = agent._create_handoff_tool(
                        target_agent_name,
                        target_agent._handoff_description,
                        tool_registry
                    )
                    handoff_tools.append(handoff_tool)

            agent.add_handoff_tools(handoff_tools)

    def get_initialized_context(self, agent_name: str, session: ConversationSession) -> Context:
        context = session.get_context(agent_name)
        agent = self.agents[agent_name]

        if not context.get_items():
            context.update(Message(role='system', content=agent._prompt))
            context.update(Message(role='developer',
                                   content="It is mandatory to greet the user and talk to them using the talk_to_user tool."))
            context.update(Message(role='user', content="Hi"))

        return context

    def start_conversation(self, initial_agent, message=None) -> ConversationSession:
        session = ConversationSession()
        session.current_agent_name = initial_agent.get_agent_name()
        current_message = message or Message(role='user', content="Hi")

        while session.conversation_active:
            current_agent = self.agents[session.current_agent_name]
            context = self.get_initialized_context(session.current_agent_name, session)

            result = current_agent.run_single_iteration(current_message, context)

            if result.type == "end":
                print(f"Conversation ended: {result.message}")
                break
            elif result.type == "handoff":
                self._handle_handoff(result, session)
                current_message = Message(role='user', content=result.handoff_message)
            elif result.type == "continue":
                current_message = None

        return session

    def _handle_handoff(self, handoff_result, session: ConversationSession):
        old_agent_name = session.current_agent_name
        new_agent_name = handoff_result.target_agent

        old_agent = self.agents[old_agent_name]

        old_context = session.get_context(old_agent_name)
        new_context = self.get_initialized_context(new_agent_name, session)

        handoff_summary = old_agent.summarize_context_for_handoff(old_context, new_agent_name)
        new_context.update(Message(role="system", content=handoff_summary))

        session.current_agent_name = new_agent_name


class Result:
    def __init__(self, result_type: Literal["continue", "handoff", "end"], message: str = "", target_agent: str = "",
                 handoff_message: str = ""):
        self.type = result_type
        self.message = message
        self.target_agent = target_agent
        self.message = handoff_message

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
