import os
from typing import Tuple, Dict

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from .tools import register_tool
from ..utils.logger import duck_logger

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@register_tool
async def make_example_tool(concept: str) -> Tuple[str, Dict[str, int]]:
    """
    This is a tool that takes in a concept and provides an example using OpenAI's completion.
    
    Args:
        concept: The concept to generate an example for
    """
    # Create a simple message history with just the concept
    duck_logger.debug("Make Example Tool is called")
    message_history = [{
        "role": "user",
        "content": f"Context = {concept}\n\n"
                   f"Please provide a detailed explanation in the following format:\n\n"
                   f"### 1. Concept Explanation:\n"
                   f"[Provide a clear, detailed explanation of the concept]\n\n"
                   f"### 2. Analogy using Fruit:\n"
                   f"[Create an analogy using fruit to illustrate the concept]\n\n"
                   f"### 3. Example Problem:\n"
                   f"[Create a practice problem to test understanding]\n\n"
                   f"Make sure to use markdown formatting with ### for section headers and proper spacing between sections."
    }]

    completion: ChatCompletion = await client.chat.completions.create(
        model='gpt-4.1-2025-04-14',
        messages=message_history,
    )

    completion_dict = completion.model_dump()

    return completion_dict['choices'][0]['message']['content'], completion_dict['usage']
