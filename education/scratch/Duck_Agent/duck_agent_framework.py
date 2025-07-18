from __future__ import annotations

import os
from typing import Literal, Optional, List, TypedDict

from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall
from pydantic import BaseModel

from education.scratch.Duck_Agent.tools import Tool, ToolRegistry


class Response(BaseModel):
    next_step: Literal['finished', 'tool_call', 'agent']
    output: str = ""


class Message(TypedDict):
    role: Literal['user', 'assistant', 'system']
    content: str


class FunctionCall(TypedDict):
    type: str
    id: str
    call_id: str
    name: str
    arguments: str


class FunctionCallOutput(TypedDict):
    type: str
    call_id: str
    output: str


class Context:
    def __init__(self, ):
        self._items: List[Message | FunctionCall | FunctionCallOutput] = []

    def update(self, new_item: Message | FunctionCall | FunctionCallOutput):
        self._items.append(new_item)

    def pop(self, index: int = -1) -> Message | FunctionCall | FunctionCallOutput:
        return self._items.pop(index)

    def get_items(self) -> List[Message | FunctionCall | FunctionCallOutput]:
        return self._items

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

    def add_handoffs(self):
        self._tools.extend(self._create_handoffs())

    def _create_handoffs(self):
        handoff_tools = []

        for handoff_agent in self.handoffs:
            if not handoff_agent:
                continue

            tool_name = f"transfer_to_{handoff_agent._name.replace(' ', '_').lower()}"

            def create_handoff_closure(target_agent):
                def handoff_tool(message: str):
                    print(f"Transferring to {target_agent._name} with message: {message}")
                    return target_agent.run(Message(role="user", content=message))

                handoff_tool.__name__ = tool_name
                return handoff_tool

            tool_func = create_handoff_closure(handoff_agent)
            tool = self._tool_registry.register(tool_func)
            tool.description = handoff_agent._handoff_description or f"Transfer to {handoff_agent._name}"
            handoff_tools.append(tool)

        return handoff_tools

    def _get_completion(self):
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

    def run(self, message: Message) -> Response:
        if not self._prompt_added:
            self._inner_context.update(Message(role='system', content=self._prompt))
            self._prompt_added = True
        self._inner_context.update(message)
        while True:
            result = self._get_completion()
            output_item = result.output[0]
            match output_item.type:
                case "message":
                    # If the output is a message
                    text_content = output_item.content[0].text
                    return Response(next_step='finished', output=text_content)
                case "function_call":
                    # If the output is a handoff
                    if output_item.name.startswith("transfer_to_"):
                        return self._tool_registry.handle_tool_call(output_item)
                    # If the output is a function call
                    else:
                        value = self._tool_registry.handle_tool_call(output_item)
                        self._add_function_call_context(value, output_item, self._inner_context)


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
    tools = ToolRegistry()
    tools.register(add)
    tools.register(concise_sentence)
    add_agent = NodeAgent(
        client=client,
        tool_registry=tools,
        name="MathAgent",
        model="gpt-4.1",
        prompt="You are a math agent. You can perform addition operations.",
        handoff_description="Handles math questions and addition operations.",
        tools=[tools.tools['add']]
    )
    subtract_agent = NodeAgent(
        client=client,
        tool_registry=tools,
        name="EnglishAgent",
        model="gpt-4.1",
        prompt="You are an english agent. You help rewrite sentences to be more concise.",
        handoff_description="Handles english questions and rewrites sentences to be more concise.",
        tools=[tools.tools['concise_sentence']]
    )
    head_agent = NodeAgent(
        client=client,
        tool_registry=tools,
        name="RouterAgent",
        model="gpt-4.1",
        prompt="You are a routing agent for math and english questions. You never answer questions directly. Instead, you route math questions to the math agent and english questions to the english agent.",
        handoff_description="Routes math questions to the math agent and english questions to the english agent."
    )

    head_agent.handoffs = [add_agent, subtract_agent]
    add_agent.handoffs = [head_agent]
    subtract_agent.handoffs = [head_agent]

    head_agent.add_handoffs()
    add_agent.add_handoffs()
    subtract_agent.add_handoffs()

    print(head_agent.run(Message(role='user', content='Tell me about sine and cosine')).output)


if __name__ == "__main__":
    main()
