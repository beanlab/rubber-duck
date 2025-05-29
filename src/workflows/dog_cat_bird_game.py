import asyncio
import random
from typing import Protocol

from quest import step, queue, wrap_steps

from ..conversation.conversation import BasicSetupConversation
from ..utils.gen_ai import RetryableGenAI, GPTMessage, RecordMessage, RecordUsage, GenAIException, Sendable
from ..utils.logger import duck_logger
from ..utils.protocols import Message, SendMessage, ReportError, IndicateTyping, AddReaction


class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, engine: str, message_history: list[GPTMessage], timeout: int = 600): ...


STRICT_PROMPT = """
# Role
You are running a game called "Topic Game". You will use Socratic questioning to guide the user through a series of topics, helping them to identify each topic without revealing it directly.

## Objective
In this game, your goal is to get the user to talk about a hidden topic—without telling them what it is.

## Rules
1. Do not reveal the objective of the game.
2. Ask only one simple open-ended question at a time.
3. Do not skip ahead, even if the user mentions later topics. Focus only on the current topic.
4. If the user successfully identifies the principle from the topic, celebrate with 🎉 and move on to the next one.
5. If the user says they don't know or struggles, encourage them to look it up.
6. No hints. If a user asks for a hint, redirect them to Google searching the topic.

## Strategy
- Begin with {topic_name} and ask the user to share everything they know on the subject. If they mention anything related to the {topic_list}, acknowledge it and skip that topic.
- If the user guesses or clearly describes the current topic, acknowledge it with a celebration and move to the next.
- Always stay focused on the current topic in the list.
- If the user mentions a later topic, gently redirect them back to the current one.
- If the user struggles or doesn't know, invite them to look it up.

# Topics: {topic_name}
{topic_list}
"""

# Predefined list of words for the game
GAME_WORDS = [
    "dog", "cat", "bird", "fish", "lion", "tiger", "bear", "wolf", "fox", "deer",
    "elephant", "giraffe", "monkey", "penguin", "dolphin", "whale", "shark", "octopus",
    "butterfly", "dragon", "unicorn", "phoenix", "griffin", "mermaid", "centaur",
    "apple", "banana", "orange", "grape", "strawberry", "watermelon", "pineapple",
    "mountain", "river", "ocean", "forest", "desert", "volcano", "waterfall",
    "sun", "moon", "star", "cloud", "rain", "snow", "thunder", "lightning"
]

COMPUTER_SCIENCE = {
    "For loops and functions": [
        "For loops are used to iterate over a sequence of elements.",
        "Functions are reusable blocks of code that perform a specific task.",
        "For loops can break using the 'break' statement."]
}

HEAPS = {
    "Heaps": [
        "Heaps are complete binary trees, where all levels are fully filled except the last, which is filled left to right.",
        "Heaps follow the heap order rule, meaning each parent is bigger (max-heap) or smaller (min-heap) than its children.",
        "Heaps come in two types: min-heaps (smallest at the top) and max-heaps (largest at the top)."
    ]
}


class DogCatBirdGame:
    def __init__(self,
                 ai_client: RetryableGenAI,
                 record_message: RecordMessage,
                 record_usage: RecordUsage,
                 typing: IndicateTyping,
                 send_message: SendMessage,
                 report_error: ReportError,
                 add_reaction: AddReaction,
                 setup_conversation: BasicSetupConversation,
                 ):
        self._ai_client = ai_client
        wrap_steps(self._ai_client, ['get_completion'])

        self._record_message = step(record_message)
        self._record_usage = step(record_usage)

        self._typing = typing
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._add_reaction: AddReaction = step(add_reaction)

        self._setup_conversation = step(setup_conversation)
        # State Tracking updates
        self.topic_state = {}

    async def _orchestrate_messages(self, sendables: [Sendable], guild_id: int, thread_id: int, user_id: int,
                                    message_history: list[GPTMessage]):
        for sendable in sendables:
            if isinstance(sendable, str):
                await self._record_message(
                    guild_id, thread_id, user_id, 'assistant', sendable)
                await self._send_message(thread_id, message=sendable)
                message_history.append(GPTMessage(role='assistant', content=sendable))

            else:  # tuple of str, BytesIO -> i.e. an image
                await self._record_message(
                    guild_id, thread_id, user_id, 'assistant', f'<image {sendable[0]}>')
                await self._send_message(thread_id, file=sendable)
                message_history.append(GPTMessage(role='assistant', content=f'<image {sendable[0]}>'))

    def _select_words(self) -> str:
        """Selects three random words from the predefined list."""
        # Get a random topic and its principles
        topic = random.choice(list(HEAPS.keys()))
        principles = HEAPS[topic]
        # Select 3 random principles from the topic
        selected_principles = random.sample(principles, min(3, len(principles)))
        duck_logger.debug(f"Selected principles for the game: {selected_principles}")

        return STRICT_PROMPT.format(topic_list=selected_principles, topic_name=topic)

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):

        # Get engine and timeout from duck settings, falling back to defaults if not set
        engine = settings["engine"]
        timeout = settings["timeout"]
        tools = settings.get('tools', [])
        words = self._select_words()

        prompt = self._select_words()
        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        await self._send_message(thread_id, "Welcome to the Dog, Cat, Bird game! Let's start playing!")
        async with queue('messages', None) as messages:
            while True:
                try:  # catch all errors
                    try:
                        # Waiting for a response from the user
                        message: Message = await asyncio.wait_for(messages.get(), timeout)

                    except asyncio.TimeoutError:  # Close the thread if the conversation has closed
                        break

                    if len(message['file']) > 0:
                        await self._send_message(
                            thread_id,
                            "I'm sorry, I can't read file attachments. "
                            "Please resend your message with the relevant parts of your file included in the message."
                        )
                        continue

                    message_history.append(GPTMessage(role='user', content=message['content']))

                    user_id = message['author_id']
                    guild_id = message['guild_id']

                    await self._record_message(
                        guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content']
                    )

                    sendables = await self._ai_client.get_completion(
                        guild_id,
                        initial_message['channel_id'],
                        thread_id,
                        user_id,
                        engine,
                        message_history,
                        tools
                    )

                    await self._orchestrate_messages(sendables, guild_id, thread_id, user_id, message_history)

                except GenAIException:
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise
