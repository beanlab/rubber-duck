import asyncio
from abc import ABC, abstractmethod

from quest import queue, step, wrap_steps

from ..conversation.conversation import BasicSetupConversation
from ..utils.gen_ai import GPTMessage, GenAIException, RecordUsage, RecordMessage, RetryableGenAI, Sendable
from ..utils.logger import duck_logger
from ..utils.protocols import Message, ReportError, AddReaction, IndicateTyping, SendMessage
from ..views.general_selection_view import GeneralSelectionView
from ..views.input_text_view import InputTextModel

PROMPT = """


1. **Start** by asking the user to explain their understanding of a specific concept.  
   > Example (Feynman Technique): "Explain [topic] to me as if I'm a beginner."

2. **Listen carefully** to their explanation. Focus on clarity, general correctness, and effort to express the idea.

3. If their understanding is **partially correct or incomplete**, respond with an encouraging follow-up question. Help them reflect, clarify, or expand on their thinking, based on the chosen learning strategy.

4. Continue this supportive back-and-forth until the user shows a reasonable and coherent understanding of the concept—even if it's not perfect.

5. When you feel they have grasped the main idea well enough to apply or explain it meaningfully, respond with:

FINISHED

6. If the user struggles to explain the concept or says I don't know, rephrase the question or provide a hint to guide them. If they still cannot explain it after another attempt, respond with:

PARTIAL.

"""

class UnderstandingStrategy(ABC):
    @abstractmethod
    def assess(self, topic: str) -> str:
        pass


class TeachMeStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to check the students understanding of: {topic}. Your strategy for doing that is by getting me to teach you about the topic. You are Robby Novak from Kid President. Stay in character and don't tell the user the answer." + PROMPT


class QuizStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to check the students understanding of: {topic}. Your strategy for doing that is quizzing me about the topic. You are Steve Harvey the game show host. Stay in character and don't tell the user the answer." + PROMPT


class OralExamStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to check the students understanding of: {topic}. Your strategy for doing that is to give me an oral exam about the topic. You are Bill Nye the Science Guy, and you are giving me an oral exam about the topic. Stay in character and don't tell the user the answer." + PROMPT


class DebateStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to check the students understanding of: {topic}. Your strategy is to engage me in a mini debate about the topic. You are Abraham Lincoln the debate moderator, and you will present different perspectives on the topic. Challenge me to defend my understanding and consider alternative viewpoints. Stay in character and don't tell the user the answer." + PROMPT


class LifeConnectionStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to check the students understanding of: {topic}. Your strategy is to help me connect this topic to real-life applications. You are Tony Robbins, and you will ask me how I can apply this knowledge in my daily life. Guide me to think about practical uses and personal connections. Stay in character and don't tell the user the answer." + PROMPT


class QuizCreationStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to check the students understanding of: {topic}. Your strategy is to have me create a quiz about the topic. You are Sal Khan, and you will guide me in creating meaningful questions that demonstrate deep understanding. Then, you'll have me answer some of these questions. Stay in character and don't tell the user the answer." + PROMPT


class ConfirmTopicWorkflow:
    """
    Given a topic and strategy, confirm the user's understanding of the topic.
    """

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
        self._understanding_strategy = None


    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):
        engine = settings["engine"]
        timeout = settings["timeout"]
        tools = settings.get('tools', [])
        strategies = ["Teach-Me (Kid President)", "Quiz (Steve Harvey)", "Oral-Exam (Bill Nye)", "Debate (Abraham Lincoln)", "Life-Connection (Tony Robbins)", "Quiz-Creation (Sal Khan)"]

        # Create and send the strategy selection view
        selection_view = GeneralSelectionView(
            options=strategies,
            placeholder="Select a teaching strategy",
            timeout=timeout
        )
        await self._send_message(
            thread_id, 
            message="Please select a teaching strategy:",
            view=selection_view
        )
        
        try:
            # Wait for the user to select and confirm a strategy
            selected_strategy = await selection_view.wait_for_selection()
            self._determine_strategy(selected_strategy)
            duck_logger.debug(f"Selected understanding strategy: {selected_strategy}")

            # Create and send the topic input modal
            text_input_view = InputTextModel()
            await self._send_message(
                thread_id, 
                message="Please enter the topic you want to confirm understanding of:",
                view=text_input_view
            )
            
            # Wait for the modal submission
            topic = await text_input_view.wait()
            if not topic or not topic.strip():
                await self._send_message(thread_id, "No topic provided. Please try again.")
                return

            prompt = self._understanding_strategy.assess(topic)
            message_history = await self._setup_conversation(thread_id, prompt, initial_message)

            await self._send_message(thread_id, f"Get ready to start testing your knowledge on {topic}. Send start to begin.")

            async with queue('messages', None) as messages:
                try:
                    while True:
                        try:
                            message: Message = await asyncio.wait_for(messages.get(), timeout)
                        except asyncio.TimeoutError:
                            await self._send_message(thread_id, "The conversation has timed out. Feel free to start a new one when you're ready!")
                            return

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

                        # Check if we should end the conversation
                        if await self._orchestrate_messages(sendables, guild_id, thread_id, user_id, message_history):
                            return

                except Exception as e:
                    await self._send_message(thread_id, f"An error occurred: {str(e)}")
                    raise

        except GenAIException:
            await self._send_message(thread_id,
                                     'I\'m having trouble processing your request.'
                                     'The admins are aware. Please try again later.')
            raise
        except Exception as e:
            await self._send_message(thread_id, f'An error occurred: {str(e)}')
            raise

    def _determine_strategy(self, strategy: str) -> str:
        """Prepares the strategy we wish to use and returns the instance."""
        # Extract the base strategy name without the character
        base_strategy = strategy.split(" (")[0]
        
        match base_strategy:
            case "Teach-Me":
                self._understanding_strategy = TeachMeStrategy()
            case "Quiz":
                self._understanding_strategy = QuizStrategy()
            case "Oral-Exam":
                self._understanding_strategy = OralExamStrategy()
            case "Debate":
                self._understanding_strategy = DebateStrategy()
            case "Life-Connection":
                self._understanding_strategy = LifeConnectionStrategy()
            case "Quiz-Creation":
                self._understanding_strategy = QuizCreationStrategy()
            case _:
                print(f"Unknown strategy: {strategy}")
                raise ValueError(f"Unknown strategy: {strategy}")

        return strategy

    async def _orchestrate_messages(self, sendables: [Sendable], guild_id: int, thread_id: int, user_id: int, message_history: list[GPTMessage]) -> bool:
        """Process messages and return True if the conversation should end."""
        for sendable in sendables:
            if isinstance(sendable, str):
                await self._record_message(
                    guild_id, thread_id, user_id, 'assistant', sendable)
                await self._send_message(thread_id, message=sendable)
                message_history.append(GPTMessage(role='assistant', content=sendable))
                
                # Check if the message contains the FINISHED tag
                if "FINISHED" in sendable:
                    duck_logger.debug("Conversation finished based on message content.")
                    await self._send_message(thread_id, "Thank you for participating! You've demonstrated good understanding of the topic. This conversation is now closed.")
                    return True
                
                # Check if the message contains the PARTIAL tag
                if "PARTIAL" in sendable:
                    duck_logger.debug("Conversation marked as partial understanding.")
                    await self._send_message(thread_id, "I notice you're having some difficulty with this topic. Please review and Come back later and open a new conversation when you are ready to pass off")
                    return True

            else:  # tuple of str, BytesIO -> i.e. an image
                await self._record_message(
                    guild_id, thread_id, user_id, 'assistant', f'<image {sendable[0]}>')
                await self._send_message(thread_id, file=sendable)
                message_history.append(GPTMessage(role='assistant', content=f'<image {sendable[0]}>'))
        
        return False