from typing import Protocol, TypedDict
from quest import step
from conversation import GPTMessage
from protocols import Message

class AgenticConfig(TypedDict):
    name: str
    engine: str
    prompt: str | None
    prompt_file: str | None
    timeout: int | None

class AgenticWorkflow:
    def __init__(self,
                 config: AgenticConfig,
                 setup_thread,
                 setup_conversation,
                 have_conversation,
                 get_feedback):
        
        self._config = config
        self._setup_thread = step(setup_thread)
        self._setup_conversation = step(setup_conversation)
        self._have_conversation = step(have_conversation)
        self._get_feedback = step(get_feedback)

    async def __call__(self, channel_name: str, initial_message: Message, timeout=600):
        # Get configuration
        engine = self._config.get('engine', 'gpt-4-turbo-preview')
        timeout = self._config.get('timeout', timeout)

        # Create system prompt for agentic capabilities
        system_prompt = """You are an agentic AI assistant that helps users by:
1. Understanding their needs through active questioning
2. Breaking down complex problems into manageable steps
3. Providing clear explanations and examples
4. Checking understanding and adjusting based on feedback

Follow these steps for each interaction:
1. Understand the user's need or problem
2. Ask clarifying questions if needed
3. Propose a solution or explanation
4. Check if the user understands
5. Adjust based on their response

Current conversation state: understanding
Remember to maintain and update the conversation state in your responses using the format:
[STATE: understanding|clarifying|teaching|assessing]"""

        # Setup thread and start conversation
        thread_id = await self._setup_thread(initial_message)
        
        # Initialize conversation with system prompt
        message_history = await self._setup_conversation(
            thread_id,
            system_prompt,
            initial_message
        )

        # Have the conversation
        await self._have_conversation(
            thread_id,
            engine,
            message_history,
            timeout
        )

        # Get feedback if configured
        if self._get_feedback:
            guild_id = initial_message['guild_id']
            user_id = initial_message['author_id']
            await self._get_feedback(
                self._config.get('name', 'agentic'),
                guild_id,
                thread_id,
                user_id
            ) 