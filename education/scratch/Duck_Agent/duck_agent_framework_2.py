from __future__ import annotations

import os
from typing import Optional, TypedDict, Literal, List, Dict

from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall, ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput

from education.scratch.Duck_Agent.tools import ToolRegistry, Tool


class Message(TypedDict):
    role: Literal['system', 'developer', 'user', 'assistant']
    content: str


class Context:
    def __init__(self):
        self._items: List[Message | ResponseFunctionToolCallParam | FunctionCallOutput] = []

    def update(self, new_item: Message | ResponseFunctionToolCallParam | FunctionCallOutput):
        self._items.append(new_item)

    def get_items(self) -> List[Message | ResponseFunctionToolCallParam | FunctionCallOutput]:
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
        self.agent_contexts: Dict[str, Context] = {}
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

    def start_conversation(self, initial_agent: Agent, message=None) -> ConversationSession:
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


class Agent:
    def __init__(self,
                 client: OpenAI,
                 tool_registry: ToolRegistry,
                 name: str,
                 model: str,
                 prompt: str,
                 handoff_description: str,
                 tools: Optional[list[Tool]] = None,
                 handoffs: Optional[list[str]] = None):

        self._name = name
        self._client = client
        self._model = model
        self._prompt = prompt
        self._handoff_description = handoff_description
        self._tool_registry = tool_registry
        self.handoff_agent_names = handoffs or []
        self._tools = tools or []

        self._tools.append(self.create_talk_to_user_tool())
        self._tools.append(self.create_end_conversation_tool())

    def add_handoff_tools(self, handoff_tools: list[Tool]):
        self._tools.extend(handoff_tools)

    def summarize_context_for_handoff(self, context: Context, agent_name: str) -> str:
        conversation = context.get_string_items()
        response = self._client.responses.create(
            model="gpt-4.1",
            instructions=(
                f"You are summarizing a conversation between a user and an assistant "
                f"to help a new agent ({agent_name}) understand the context before continuing. "
                f"Focus on the following:\n"
                f"- What the user has asked or discussed so far\n"
                f"- How the assistant has responded, including relevant conclusions, tools used, or next steps\n"
                f"- Any unresolved questions, goals, or tasks that the new agent may need to address\n\n"
                f"Write the summary in a clear, concise, and informative way. "
                f"Do not omit important technical details or user intent. "
                f"This summary should allow the {agent_name} agent to take over seamlessly.\n\n"
            ),
            input=conversation
        )
        return response.output_text

    def create_talk_to_user_tool(self):
        def talk_to_user(output: str) -> str:
            """
            A tool to interact with the user directly. Call this tool to continue the conversation with the user.
            :param output: The agent's output to the user or in other words the assistants response to the last user response.
            :return input: The user's response to the agent's output.
            """
            print(f"Agent: {output}")
            inpt = input("You: ")
            return inpt

        return self._tool_registry.register(talk_to_user)

    def create_end_conversation_tool(self):
        def end_conversation(reason: str) -> str:
            """
            End the conversation gracefully. Use this when the task is complete,
            no further assistance is needed, or the conversation has reached a natural conclusion.
            :param reason: Brief explanation of why the conversation is ending
            :return: Confirmation that conversation will end
            """
            return f"END_CONVERSATION: {reason}"

        return self._tool_registry.register(end_conversation)

    def _create_handoff_tool(self, target_agent_name: str, target_agent_description: str,
                             tool_registry: ToolRegistry) -> Tool:
        tool_name = f"transfer_to_{target_agent_name.replace(' ', '_').lower()}"

        def handoff_tool(message: str):
            """
            A tool to transfer the conversation to another agent with a message.
            :param message:
            :return:
            """
            return target_agent_name, message

        handoff_tool.__name__ = tool_name
        tool = tool_registry.register(handoff_tool)
        tool.description = target_agent_description or f"Transfer to {target_agent_name}"
        return tool

    def _get_completion(self, context: Context):
        return self._client.responses.create(
            model=self._model,
            input=context.get_items(),
            tools=[tool.to_openai_tool() for tool in self._tools],
        )

    def _add_function_call_context(self, result: str, call: ResponseFunctionToolCall, context: Context):
        function_call = ResponseFunctionToolCallParam(
            type="function_call",
            id=call.id,
            call_id=call.call_id,
            name=call.name,
            arguments=call.arguments
        )

        function_call_output = FunctionCallOutput(
            type="function_call_output",
            call_id=call.call_id,
            output=str(result)
        )
        context.update(function_call)
        context.update(function_call_output)

    def run_single_iteration(self, message, context: Context) -> Result:
        result = self._get_completion(context)
        output_item = result.output[0]
        match output_item.type:
            case "message":
                text_content = output_item.content[0].text
                response = self._tool_registry.get_tool("talk_to_user").run(output=text_content)
                context.update(Message(role='assistant', content=text_content))
                context.update(Message(role='user', content=response))
                return Result("continue")

            case "function_call":
                if output_item.name.startswith("transfer_to_"):
                    target_agent, handoff_message = self._tool_registry.handle_tool_call(output_item)
                    return Result("handoff", target_agent=target_agent, handoff_message=handoff_message)

                elif output_item.name == "end_conversation":
                    result_str = self._tool_registry.handle_tool_call(output_item)
                    return Result("end", message=result_str)

                else:
                    value = self._tool_registry.handle_tool_call(output_item)
                    self._add_function_call_context(value, output_item, context)
                    return Result("continue")

        return Result("continue")

    def get_agent_name(self):
        return self._name


def main():
    def add(a: int, b: int) -> int:
        """Adds two integers."""
        print("Adding two integers...")
        return a + b

    def concise_sentence(sentence: str) -> str:
        """Rewrites a sentence to be more concise."""
        print("Rewriting sentence to be more concise...")
        return ' '.join(sentence.split())

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    registry = ToolRegistry()

    registry.register(add)
    registry.register(concise_sentence)

    router_agent = Agent(
        client=client,
        tool_registry=registry,
        name="RouterAgent",
        model="gpt-4.1",
        prompt="IMMEDIATELY greet the user and talk to them using the talk_to_user tool. You are a routing agent for math and english questions. Continue talking back and forth with the user until the user mentions a question regarding math or english subjects, then hand off. You answer any question that does not have to do with math or english. If a question is about math, you route it to the math agent. If a question is about english, you route it to the english agent.",
        handoff_description="When the user asks about math or english, hand off to the correct agent.",
        handoffs=["MathAgent", "EnglishAgent"]
    )

    math_agent = Agent(
        client=client,
        tool_registry=registry,
        name="MathAgent",
        model="gpt-4.1",
        prompt="You are a math agent. IMMEDIATELY greet the user and talk to them using the talk_to_user tool. You can perform addition operations. When you have fully answered the user's math question, you can either continue helping with more math questions or hand off back to the routing agent if the user wants to discuss other topics.",
        tools=[registry.tools['add']],
        handoff_description="If the user asks a question that does not relate to math, hand off to the routing agent.",
        handoffs=["RouterAgent"]
    )

    english_agent = Agent(
        client=client,
        tool_registry=registry,
        name="EnglishAgent",
        model="gpt-4.1",
        prompt="You are an english agent. IMMEDIATELY greet the user and talk to them using the talk_to_user tool. You help rewrite sentences to be more concise. When you have fully answered the user's english question, you can either continue helping with more english questions or hand off back to the routing agent if the user wants to discuss other topics.",
        tools=[registry.tools['concise_sentence']],
        handoff_description="If the user asks a question that does not relate to english, hand off to the routing agent.",
        handoffs=["RouterAgent"]
    )

    coordinator = AgentCoordinator()

    coordinator.register_agent(router_agent)
    coordinator.register_agent(math_agent)
    coordinator.register_agent(english_agent)

    coordinator.setup_handoffs(registry)

    coordinator.start_conversation(router_agent)


if __name__ == "__main__":
    main()
