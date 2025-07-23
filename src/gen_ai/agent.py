import os
from typing import Optional, Literal

from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall, ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput

from education.scratch.Duck_Agent.context import Context, Message
from education.scratch.Duck_Agent.tools import ToolRegistry, Tool

class Result:
    def __init__(self, result_type: Literal["continue", "handoff", "end"], message: str = "", target_agent: str = "",
                 handoff_message: str = ""):
        self.type = result_type
        self.message = message
        self.target_agent = target_agent
        self.handoff_message = handoff_message

class Agent:
    def __init__(self,
                 name: str,
                 model: str,
                 prompt: str,
                 handoff_description: str,
                 tool_registry: ToolRegistry,
                 tools: Optional[list[Tool]] = None,
                 handoffs: Optional[list[str]] = None):

        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._name = name
        self._model = model
        self._prompt = prompt
        self._handoff_description = handoff_description
        self._tool_registry = tool_registry
        self.handoff_agent_names = handoffs or []
        self._tools = tools or []

    def add_handoff_tools(self, handoff_tools: list[Tool]):
        self._tools.extend(handoff_tools)

    def summarize_context_for_handoff(self, context: Context, agent_name: str) -> str:
        conversation = context.get_string_items()
        response = self._client.responses.create(
            model="gpt-4.1-mini-2025-04-14",
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

    def run_single_iteration(self, context: Context) -> Result:
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