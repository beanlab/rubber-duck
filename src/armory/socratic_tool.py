from .tools import register_tool

def make_socratic_tool(conversation_instance):
    @register_tool
    async def socratic_tool(concept: str, guild_id: int, channel_id: int, thread_id: int, author_id: int, message_id: int) -> str:
        prompt = f"Let's discuss the concept: {concept}"
        settings = {
            "prompt_file": None,
            "engine": "gpt-4",
            "timeout": 600,
            "tools": None,
            "introduction": "Let's begin our discussion."
        }
        initial_message = {
            "content": prompt,
            "author_id": author_id,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "file": []
        }
        await conversation_instance(thread_id, settings, initial_message)
        return "Conversation started with a new prompt."
    return socratic_tool



