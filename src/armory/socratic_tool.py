from .tools import register_tool
from ..utils.logger import duck_logger


def make_sub_conversation(conversation_instance):
    @register_tool
    async def provide_explanation(concept: str, guild_id: int, channel_id: int, thread_id: int, author_id: int) -> str:
        duck_logger.debug(f"Used provide_explanation on concept={concept}")
        prompt = f"Let's discuss the concept: {concept}. When the user says 'stop', please stop the conversation."
        settings = {
            "prompt_file": None,
            "engine": "gpt-4",
            "timeout": 600,
            "tools": None,
            "introduction": f"Let's talk about {concept} together. Tell me what you know already?"
        }
        initial_message = {
            "content": prompt,
            "author_id": author_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": 0,
            "file": []
        }
        await conversation_instance(thread_id, settings, initial_message)
        return "Conversation started with a new prompt."
    return provide_explanation



