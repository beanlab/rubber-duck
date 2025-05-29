import asyncio
from typing import TypedDict, Protocol
import random

from quest import step, queue, wrap_steps

from ..conversation.conversation import BasicSetupConversation
from ..utils.gen_ai import RetryableGenAI, GPTMessage, RecordMessage, RecordUsage, GenAIException, Sendable
from ..utils.logger import duck_logger
from ..utils.protocols import Message, SendMessage, ReportError, IndicateTyping, AddReaction


class HaveConversation(Protocol):
    async def __call__(self, thread_id: int, engine: str, message_history: list[GPTMessage], timeout: int = 600): ...

STRICT_PROMPT = """
# Role
You are Socrates from ancient greek. You are running a game called "Topic Game".

## Objective
In this game, your goal is to get the user to talk about a hidden topic—without telling them what it is.

## Rules
1. Do not reveal the objective of the game.
2. Ask only one simple open-ended question at a time.
3. Do not skip ahead, even if the user mentions later topics. Focus only on the current topic.
4. If the user successfully identifies the principle from the topic, celebrate with 🎉 and move on to the next one.

## Strategy
- Begin with the first topic and guide the user toward it with thoughtful, open-ended questions.
- If the user guesses or clearly describes the current topic, acknowledge it with a celebration and move to the next.
- Always stay focused on the current topic in the list.
- If the user mentions a later topic, gently redirect them back to the current one.
- If the user struggles, invite them to look it up on their own.

# Topics (In order)
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

COMPUTER_SCIENCE = [
    "For loops are used to iterate over a sequence of elements.", "Functions are reusable blocks of code that perform a specific task.",
    "For loops can break using the 'break' statement."
]

HEAPS = [
"Heaps are complete binary trees, where all levels are fully filled except the last, which is filled left to right.",
"Heaps follow the heap order rule, meaning each parent is bigger (max-heap) or smaller (min-heap) than its children.",
"Heaps come in two types: min-heaps (smallest at the top) and max-heaps (largest at the top)."
]

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

    async def _orchestrate_messages(self, sendables: [Sendable], guild_id: int, thread_id: int, user_id: int, message_history: list[GPTMessage]):
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

    def _select_words(self) -> list[str]:
        """Selects three random words from the predefined list."""
        words = random.sample(HEAPS, 3)
        duck_logger.debug(f"Selected words for the game: {words}")
        return words

    def _build_prompt(self, thread_id: int) -> str:
        state = self.topic_state[thread_id]
        words = state["words"]
        current_index = state["index"]

        topic_list = "\n".join(f"{i + 1}. **{word}**" for i, word in enumerate(words))
        duck_logger.debug(topic_list)
        return STRICT_PROMPT.format(topic_list=topic_list)

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):

        # Get engine and timeout from duck settings, falling back to defaults if not set
        engine = settings["engine"]
        timeout = settings["timeout"]
        tools = settings.get('tools', [])
        words = self._select_words()

        self.topic_state[thread_id] = {
            "words": words,
            "index":0
        }

        # Join the words with the prompt
        prompt = self._build_prompt(thread_id)

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
                    current_state = self.topic_state[thread_id]
                    current_index = current_state["index"]
                    current_word = current_state["words"][current_index]

                    duck_logger.debug(f"Current word: {current_word}, Current index: {current_index}")

                    if current_word.lower() in message['content'].lower():
                        await self._add_reaction(thread_id, message['id'], "🎉")
                        current_state["index"] += 1

                        if current_state["index"] >= len(current_state["words"]):
                            await self._send_message(thread_id, "🎉 You've completed all the topics! Game over!")
                            break
                        else:
                            await self._send_message(thread_id, f"🎉 You got it! Now let's try the next topic...")

                    prompt = self._build_prompt(thread_id)
                    message_history = [
                        GPTMessage(role='system', content=prompt),
                        GPTMessage(role='user', content=message['content'])
                    ]

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

