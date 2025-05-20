import os
from typing import Tuple, Dict, Callable, Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from .tools import register_tool
from ..utils.logger import duck_logger

def create_explanation_tool(completion_tool: Callable):
    @register_tool
    async def provide_explanation(concept: str, ) -> str:
        """
        This is a tool that takes in a concept and provides an example using OpenAI's completion.

        """
        # Create a simple message history with just the concept
        duck_logger.debug("Make Example Tool is called")
        prompt = f"Context = {concept}\n\n" \
                       f"Please provide a detailed explanation in the following format:\n\n" \
                       f"### 1. Concept Explanation:\n" \
                       f"[Provide a clear, detailed explanation of the concept]\n\n" \
                       f"### 2. Analogy using Fruit:\n" \
                       f"[Create an analogy using fruit to illustrate the concept]\n\n" \
                       f"### 3. Example Problem:\n" \
                       f"[Create a practice problem to test understanding]\n\n" \
                       f"Make sure to use markdown formatting with ### for section headers and proper spacing between sections."
        return await completion_tool(prompt)
    return provide_explanation


