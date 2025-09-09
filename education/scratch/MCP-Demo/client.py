import asyncio
import json
from typing import Optional, Any, List, Dict

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AsyncOpenAI
from openai.types.responses import ResponseFunctionToolCallParam
from openai.types.responses.response_input_item import FunctionCallOutput

load_dotenv("../../../.env")

prompt = """
    You are an AI assistant that performs simple math calculations. You always use the provided tools to perform calculations.
    You must not perform any calculations yourself. You must always use the tools.
"""


class MCPOpenAIClient:

    def __init__(self, model: str = "gpt-4o", session: Optional[ClientSession] = None):
        self.session: Optional[ClientSession] = session
        self.openai_client = AsyncOpenAI()
        self.model = model

    async def _get_mcp_tools(self) -> List[Dict[str, Any]]:
        tools_result = await self.session.list_tools()
        tools = []
        for tool in tools_result.tools:
            schema = tool.inputSchema
            schema["additionalProperties"] = False
            tools.append({
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": schema,
                "strict": True
            })
        return tools

    async def _process_query(self, history) -> str:
        tools = await self._get_mcp_tools()

        response = await self.openai_client.responses.create(
            model=self.model,
            instructions=prompt,
            input=history,
            tools=tools
        )

        for item in response.output:
            if item.type == "function_call":
                result = await self.session.call_tool(
                    item.name,
                    arguments=json.loads(item.arguments),
                )
                history.extend([
                    ResponseFunctionToolCallParam(
                        type="function_call",
                        id=item.id,
                        call_id=item.call_id,
                        name=item.name,
                        arguments=item.arguments
                    ),
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=item.call_id,
                        output=str(result)
                    )])

                final_response = await self.openai_client.responses.create(
                    model=self.model,
                    instructions=prompt,
                    input=history,
                    tools=tools
                )

                return final_response.output_text

            elif item.type == "message":
                return response.output_text
        return "I'm sorry, I couldn't process your request."

    async def have_conversation(self):
        history = []
        while True:
            query = input("Enter your math query (or 'exit' to quit): ")
            if query.lower() == 'exit':
                break
            else:
                history.append({"role": "user", "content": query})
                response = await self._process_query(history)
                print(f"AI: {response}")


async def main():
    async with sse_client(f"http://localhost:8050/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            client = MCPOpenAIClient(model="gpt-4o", session=session)
            await client.have_conversation()


if __name__ == "__main__":
    asyncio.run(main())
