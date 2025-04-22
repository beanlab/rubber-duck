import asyncio
import os
from textwrap import wrap

from agents import (
    Agent,
    Runner,
    TResponseInputItem,
    function_tool,
    trace, MessageOutputItem,
    ItemHelpers,
)

from pydantic import BaseModel
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
OPENAI_API_KEY = ""

class ResponseItem(BaseModel):
    is_conversation_done: bool
    "If the conversation is done, set this to true"
    reply: str
    "The response to the user"

name="Chatbot agent"
model="gpt-4.1"
loop_instructions=f"""
{RECOMMENDED_PROMPT_PREFIX}

You are a CS tutor. Always:
1. Keep answers very short (1–2 sentences).
2. Ask the student to explain their thinking before you hint.
3. Give hints only—never full solutions.
4. If they ask for answers, redirect back to their reasoning.
5. Clarify concepts they don’t understand.

If the conversation is done, the output type should be set to True. If the conversation isn't finished, the output type should be set to False.
"""
tool_instructions = f"""
{RECOMMENDED_PROMPT_PREFIX}
You are a CS tutor. Always:
1. Keep answers very short (1–2 sentences).
2. Ask the student to explain their thinking before you hint.
3. Give hints only—never full solutions.
4. If they ask for answers, redirect back to their reasoning.
5. Clarify concepts they don’t understand.

You interact with people via tools called `message_user(message)` and `get_user_response`.
Whenever you need to say something, call the message_user tool. When you need a reply from the user use the get_user_response tool.
Begin by calling sending a message with message_user and getting a response with get_user_response.

Talk to the student until the conversation is over.
"""
@function_tool
async def message_user(message: str) -> None:
    """Talk to the user by sending a message.

        Args:
            message: The message you want to send to the user.

        Returns: None
    """

    print(message)

@function_tool
async def get_user_response() -> str:
    """Get a response back from the user


        Returns: The user's response as a string
    """

    print('Response: ')
    lines = []
    while True:
        lines.append(input())
        if not any(lines[-3:]):
            break
    print('------------')
    return '\n'.join(lines)

tool_agent = Agent(
    name=name,
    tools=[get_user_response, message_user],
    instructions = tool_instructions,
    model=model
)

loop_agent = Agent(
    name=name,
    instructions=loop_instructions,
    model=model,
    output_type=ResponseItem
)

async def main():
    global total_prompt_tokens, total_completion_tokens
    with trace("Tool Agent"):
        print('!!!!!!!!!!!!!! Tool Agent !!!!!!!!!!!!!!')
        input_items = [{"role": "system", "content": ""}, {"role": "user", "content": ""}]
        result = await Runner.run(tool_agent, input_items, max_turns=30)

    with trace("Loop Agent"):
        print('!!!!!!!!!!!!!! Loop Agent !!!!!!!!!!!!!!')
        while True:
            if input_items:
                result = await Runner.run(loop_agent, input_items)
                input_items = result.to_input_list()

                result = result.final_output
                reply = result.reply
                is_conversation_done = result.is_conversation_done

                print(reply)

                if is_conversation_done: break



            print("👤 You: ")
            lines = []
            while True:
                lines.append(input())
                if not any(lines[-3:]):
                    break
            print('------------')
            user_input = '\n'.join(lines)
            input_items.append({"content": user_input, "role": "user"})


if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    asyncio.run(main())