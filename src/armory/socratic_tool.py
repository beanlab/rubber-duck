from .tools import register_tool
from ..utils.logger import duck_logger

class SocraticTool:
    """A tool for Socratic questioning, allowing users to explore concepts through conversation."""

    @register_tool
    def socratic_questioning(self) -> dict:
        """Initiates a Socratic questioning session to help users think through concepts."""
        duck_logger.debug("Used socratic_questioning tool")
        
        prompt = """Let's discuss a concept together using Socratic questioning. 
        You will:
        1. Ask open-ended questions to guide thinking
        2. Help users discover answers through their own reasoning
        3. Challenge assumptions and explore implications
        4. Never provide direct answers
        
        When the user says 'stop', please stop the conversation."""
        
        settings = {
            "prompt_file": None,
            "engine": "gpt-4",
            "timeout": 600,
            "tools": None,
            "introduction": """I'll help you think through this concept using Socratic questioning.
            I'll ask questions to guide your thinking, but won't provide direct answers.
            What would you like to explore?"""
        }
        
        return {"prompt": prompt, "settings": settings}

    @register_tool
    def give_explanation(self) -> dict:
        """Provides a clear, direct explanation of a concept."""
        duck_logger.debug("Used give_explanation tool")
        
        prompt = """Provide a clear, concise explanation of the concept.
        You should:
        1. Explain the concept directly and clearly
        2. Use simple language and examples
        3. Break down complex ideas into simpler parts
        4. End with a question to check understanding
        
        When the user says 'stop', please stop the conversation."""
        
        settings = {
            "prompt_file": None,
            "engine": "gpt-4",
            "timeout": 600,
            "tools": None,
            "introduction": """I'll provide a clear explanation of the concept.
            I'll use simple language and examples to help you understand.
            What would you like me to explain?"""
        }
        
        return {"prompt": prompt, "settings": settings}

    @register_tool
    def end_conversation(self) -> dict:
        """Ends the current conversation session."""
        duck_logger.debug("Used end_conversation tool")
        
        prompt = """End the current conversation session.
        You should:
        1. Acknowledge the end of the session
        2. Summarize key points discussed
        3. Thank the user for the conversation
        
        This will end the conversation immediately."""
        
        settings = {
            "prompt_file": None,
            "engine": "gpt-4",
            "timeout": 60,
            "tools": None,
            "introduction": "Ending the conversation session."
        }
        
        return {"prompt": prompt, "settings": settings}

    # def make_sub_conversation(self, conversation_instance):
    #     @register_tool
    #     async def provide_explanation(concept: str, guild_id: int, channel_id: int, thread_id: int, author_id: int) -> str:
    #         duck_logger.debug(f"Used provide_explanation on concept={concept}")
    #
    #         # Define the base prompt that includes both Socratic questioning and explanation capabilities
    #         prompt = f"""Let's discuss the concept: {concept}.
    #         You can:
    #         1. Ask Socratic questions to help the user think through the concept
    #         2. Provide explanations when explicitly asked
    #         3. Use examples to illustrate the concept
    #         4. Guide the user through step-by-step understanding
    #
    #         When the user says 'stop', please stop the conversation.
    #         When the user asks for an explanation, provide a clear, concise explanation followed by a Socratic question to deepen understanding."""
    #
    #         settings = {
    #             "prompt_file": None,
    #             "engine": "gpt-4",
    #             "timeout": 600,
    #             "tools": None,
    #             "introduction": f"""Let's explore {concept} together.
    #             I can help you understand this concept through:
    #             - Asking questions to guide your thinking
    #             - Providing explanations when you ask
    #             - Using examples to illustrate ideas
    #             - Breaking down complex ideas into simpler parts
    #
    #             What would you like to know about {concept}?"""
    #         }
    #
    #         initial_message = {
    #             "content": prompt,
    #             "author_id": author_id,
    #             "guild_id": guild_id,
    #             "channel_id": channel_id,
    #             "message_id": 0,
    #             "file": []
    #         }
    #
    #         await conversation_instance(thread_id, settings, initial_message)
    #         return "Conversation started with a new prompt."
    #     return provide_explanation



