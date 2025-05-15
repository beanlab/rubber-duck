from .tools import register_tool
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..utils.gen_ai import OpenAI

@register_tool
async def make_example_tool(concept: str) -> str:
    """
    This is a tool that takes in a concept and provides an example using OpenAI's completion.
    
    Args:
        concept: The concept to generate an example for
    """
    # Create a simple message history with just the concept
    message_history = [{
        "role": "user",
        "content": f"Please provide a clear example for the concept: {concept}"
    }]
    
    # Get the OpenAI client and context
    from ..utils.gen_ai import OpenAI  # Import here to avoid circular dependency
    openai_client, context = OpenAI.get_current()
    
    # Get completion using the OpenAI client
    completion = await openai_client._get_completion_with_usage(
        guild_id=context["guild_id"],
        parent_channel_id=context["parent_channel_id"],
        thread_id=context["thread_id"],
        user_id=context["user_id"],
        engine=context["engine"],
        message_history=message_history,
        functions=[]  # No function calls needed for this example
    )
    
    # Extract the response from the completion
    example = completion.choices[0].message.content
    
    return example