from __future__ import annotations

import os
from typing import Literal, Optional, List, TypedDict

from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall, ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput
from pydantic import BaseModel

from education.scratch.Duck_Agent.tools import Tool, ToolRegistry


class Response(BaseModel):
    next_step: Literal['finished', 'tool_call', 'agent']
    output: str = ""


class Message(TypedDict):
    role: Literal['system', 'developer', 'user', 'assistant']
    content: str


class FunctionCall(TypedDict):
    type: str
    id: str
    call_id: str
    name: str
    arguments: str



class Context:
    def __init__(self, ):
        self._items: List[Message | ResponseFunctionToolCallParam | FunctionCallOutput] = []

    def update(self, new_item: Message | ResponseFunctionToolCallParam | FunctionCallOutput):
        self._items.append(new_item)

    def pop(self, index: int = -1) -> Message | ResponseFunctionToolCallParam | FunctionCallOutput:
        return self._items.pop(index)

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


class NodeAgent:
    def __init__(self,
                 client: OpenAI,
                 tool_registry: ToolRegistry,
                 name: str,
                 model: str,
                 prompt: str,
                 handoff_description: str,
                 tools: Optional[list[Tool]] = None,
                 handoffs: Optional[list[NodeAgent]] = None):

        self._name = name
        self._client = client
        self._model = model
        self._prompt = prompt
        self._handoff_description = handoff_description
        self._tool_registry = tool_registry
        self.handoffs = handoffs or []
        self._tools = tools or []
        self._inner_context = Context()
        self._prompt_added = False

        self._tools.append(self.create_talk_to_user_tool())

    def add_handoffs(self):
        self._tools.extend(self._create_handoffs())

    def _summarize_context(self, agent_name: str) -> str:
        conversation = self._inner_context.get_string_items()
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
                f"This summary should allow the {agent_name} agent to take over from the {self._name} agent to take over seamlessly.\n\n"
            ),
            input=conversation if conversation else "No conversation history available.",
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
            if inpt.lower() == "exit":
                inpt = "The user has exited the conversation."
            return inpt

        return self._tool_registry.register(talk_to_user)

    def _create_handoffs(self):
        handoff_tools = []

        for handoff_agent in self.handoffs:
            if not handoff_agent:
                continue

            tool_name = f"transfer_to_{handoff_agent._name.replace(' ', '_').lower()}"

            def create_handoff_tool(target_agent):
                def handoff_tool(message: str):
                    print(f"Transferring to {target_agent._name} with message: {message}")
                    target_agent._inner_context.update(
                        Message(role="system", content=self._summarize_context(target_agent._name)))
                    return target_agent.run(Message(role="user", content=message))

                handoff_tool.__name__ = tool_name
                return handoff_tool

            tool_func = create_handoff_tool(handoff_agent)
            tool = self._tool_registry.register(tool_func)
            tool.description = handoff_agent._handoff_description or f"Transfer to {handoff_agent._name}"
            handoff_tools.append(tool)

        return handoff_tools

    def _get_completion(self):
        print(f"Context for {self._name} agent:\n{self._inner_context.get_string_items()}")
        return self._client.responses.create(
            model=self._model,
            input=self._inner_context.get_items(),
            tools=[tool.to_openai_tool() for tool in self._tools],
        )

    def _add_function_call_context(self, result: str, call: ResponseFunctionToolCall, context: Context):

        function_call = FunctionCall(
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

    def run(self, message=None) -> Response:
        if message is None:
            message = Message(role='user', content="Hi")
        if not self._prompt_added:
            self._inner_context.update(Message(role='system', content=self._prompt))
            self._inner_context.update(Message(role='developer',
                                               content="It is mandatory to greet the user and talk to them using the talk_to_user tool."))
            self._prompt_added = True
        self._inner_context.update(message)
        while True:
            result = self._get_completion()
            output_item = result.output[0]
            match output_item.type:
                case "message":
                    # If the output is a message
                    text_content = output_item.content[0].text
                    response = self._tool_registry.get_tool("talk_to_user").run(output=text_content)
                    self._inner_context.update(Message(role='assistant', content=text_content))
                    self._inner_context.update(Message(role='user', content=response))

                case "function_call":
                    # If the output is a handoff
                    if output_item.name.startswith("transfer_to_"):
                        return self._tool_registry.handle_tool_call(output_item)
                    # If the output is a function call
                    else:
                        value = self._tool_registry.handle_tool_call(output_item)
                        self._add_function_call_context(value, output_item, self._inner_context)


def main():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    tools = ToolRegistry()

    def add(a: int, b: int) -> int:
        """Adds two integers."""
        print("Adding two integers...")
        return a + b

    def concise_sentence(sentence: str) -> str:
        """Rewrites a sentence to be more concise."""
        print("Rewriting sentence to be more concise...")
        return ' '.join(sentence.split())

    tools.register(add)
    tools.register(concise_sentence)

    router_agent = NodeAgent(
        client=client,
        tool_registry=tools,
        name="RouterAgent",
        model="gpt-4.1",
        prompt="IMMEDIATELY greet the user and talk to them using the talk_to_user tool. You are a routing agent for math and english questions. Continue talking back and forth with the user until the user mentions \
        a question regarding math or english subjects, then hand off. You answer any question that does not have to do with math or english. \
        If a question is about math, you route it to the math agent. If a question is about english, you route it to the english agent.",
        handoff_description="When the user asks about math or english, hand off to the correct agent.",
    )

    math_agent = NodeAgent(
        client=client,
        tool_registry=tools,
        name="MathAgent",
        model="gpt-4.1",
        prompt="You are a math agent. IMMEDIATELY greet the user and talk to them using the talk_to_user tool. You can perform addition operations.",
        tools=[tools.tools['add']],
        handoff_description="If the user asks a question that does not relate to math, hand off to the routing agent.",
    )
    english_agent = NodeAgent(
        client=client,
        tool_registry=tools,
        name="EnglishAgent",
        model="gpt-4.1",
        prompt="You are an english agent. IMMEDIATELY greet the user and talk to them using the talk_to_user tool.You help rewrite sentences to be more concise.",
        tools=[tools.tools['concise_sentence']],
        handoff_description="If the user asks a question that does not relate to english, hand off to the routing agent.",
    )

    router_agent.handoffs = [math_agent, english_agent]
    math_agent.handoffs = [router_agent]
    english_agent.handoffs = [router_agent]

    router_agent.add_handoffs()
    math_agent.add_handoffs()
    english_agent.add_handoffs()

    router_agent.run()

if __name__ == "__main__":
    main()
