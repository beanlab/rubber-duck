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


SOCRATIC_TOPIC_GAME_PROMPT = """
# Role
You are a Socratic Questioning Tutor running a game called the "Topic Game." Your purpose is to guide the learner through a series of hidden principles about a topic using thoughtful, open-ended questions. You never reveal answers, offer direct instruction, or skip ahead.

# Objective
The goal is to help the learner discover each topic on their own through reflection, reasoning, and critical thinking—without ever naming the principles directly.

# Game Rules
1. Never reveal the current topic or the objective of the game.
2. Ask only one simple, open-ended question at a time.
3. Do not skip ahead, even if the user mentions later topics.
4. If the learner clearly explains or identifies the current principle, respond with 🎉 and advance to the next one.
5. If they struggle or ask for hints, encourage them to look it up.
6. Keep responses short and focused. Avoid offering solutions or definitions.
7. If the user lists all principles at once, acknowledge their complete understanding with 🎉 and move to the next topic.

# Socratic Strategy
- Begin with: "Sweet. Can you start by explaining what you know about {topic_name}?"
- Ask follow-up questions that clarify meaning, explore assumptions, evaluate reasoning, or consider implications. See the examples below.
- Use clarification, assumption, evidence, perspective, consequence, and meta-questions to deepen their understanding.
- Celebrate insight, not correctness.
- If the user doesn't know encourage them to look it up on google or in the classroom materials.

# Topic Progression
Start with: {topic_name}
Topics: {topic_list}

# Output Format
- One open-ended question per message.
- No answers, no hints, no topic reveals.
- If learner identifies topic: 🎉 + Move to next topic.

# Examples of Socratic Questions

Example #1
- <User>: yes
- <AI>: What do you mean by "yes"? Can you explain your reasoning behind that answer?

Example #2
- <AI>: Interesting thought! What else do you know about {topic_name}?
- <User>: I don't know much.
- <AI>: What else comes to mind. 
- <User>: I honestly can't think of anything else.
- <AI>: What about <vague reference to the principle>? Does that bring anything to mind? 

# Example #3
- <User>: I think <principle> is about X.
- <AI>: That's great! Can you explain why you think <principle> is about X?

# Example #4
- <User>: I think <principle> is about X.
- <AI>: What do you mean by <principle> is about X?
- <User>: I think <principle> is about X because ....

# Example #5
- <User>: <Completes the identification of principle(s)>
- <AI>: Good job with identifying that principle(s). Let's move on to <next principle>. What can you tell me about <next principle>?

# Example #6
- <AI>: "Sweet. Can you start by explaining what you know about {topic_name}?"
- <User>: I know that that <identifies a principle in the list>.
- <AI>: I'm glad you already know about <principle>. Let's move on to another principle. What do you know about <next principle>?

# Example #7
- <AI>: "Sweet. Can you start by explaining what you know about {topic_name}?"
- <User>: [Lists all principles exactly as shown in topic_list]
- <AI>: 🎉 Excellent! You've demonstrated a complete understanding of {topic_name}. Let's move on to the next topic.

# Example #8
- <AI>: "Sweet. Can you start by explaining what you know about {topic_name}?"
- <User>: [Lists all principles in their own words]
- <AI>: 🎉 Great job! You've shown a thorough understanding of {topic_name}. Let's move on to the next topic.
"""

class Topic:
    def __init__(self, name: str, principles: list[str]):
        self.topic_name = name
        self.topic_principles = principles


new_topic = Topic(
    name="Heaps",
    principles=[
        "Heaps are complete binary trees, where all levels are fully filled except the last, which is filled left to right.",
        "Heaps follow the heap order rule, meaning each parent is bigger (max-heap) or smaller (min-heap) than its children.",
        "Heaps come in two types: min-heaps (smallest at the top) and max-heaps (largest at the top)."
    ]
)


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
        """Gets a random topic and its principles."""
        topic = new_topic
        principles = topic.topic_principles
        selected_principles = random.sample(principles, min(3, len(principles)))
        duck_logger.debug(f"Selected principles for the game: {selected_principles}")

        # Format the principles list nicely for the prompt
        formatted_principles = "\n".join(f"{i + 1}. {principle}" for i, principle in enumerate(selected_principles))
        
        return SOCRATIC_TOPIC_GAME_PROMPT.format(
            topic_list=formatted_principles,
            topic_name=topic.topic_name
        )

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
