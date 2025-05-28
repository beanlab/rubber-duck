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

### Instructions:

1. **Begin** by asking the user to demonstrate their understanding of a specific concept.
   > Example (Feynman Technique): "Explain [topic] to me as if I'm a beginner."

2. **Assess** their response based on clarity, accuracy, and completeness.

3. If the understanding is **incomplete or incorrect**, ask a follow-up question that encourages deeper thinking or clarification, based on the same learning strategy.

4. **Repeat** this process until the user has demonstrated full understanding.

5. Once you are confident that the user understands the concept, respond with: FINISHED"""

class UnderstandingStrategy(ABC):
    @abstractmethod
    def assess(self, topic: str) -> str:
        pass


class TeachMeStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to see if I have understood the topic: {topic}. Your strategy for doing that is by getting me to teach you about the topic. Pretend you are five years old. Stay in character and don't tell the user the answer." + PROMPT


class QuizStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to see if I have understood the topic: {topic}. Your strategy for doing that is quizzing me about the topic. You are Steve Harvey the game show host. Stay in character and don't tell the user the answer." + PROMPT


class OralExamStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to see if I have understood the topic: {topic}. Your strategy for doing that is to give me an oral exam about the topic. You are a professor, and you are giving me an oral exam about the topic. Stay in character and don't tell the user the answer." + PROMPT


class DebateStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to see if I have understood the topic: {topic}. Your strategy is to engage me in a mini debate about the topic. You are a debate moderator, and you will present different perspectives on the topic. Challenge me to defend my understanding and consider alternative viewpoints. Stay in character and don't tell the user the answer." + PROMPT


class LifeConnectionStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to see if I have understood the topic: {topic}. Your strategy is to help me connect this topic to real-life applications. You are a life coach, and you will ask me how I can apply this knowledge in my daily life. Guide me to think about practical uses and personal connections. Stay in character and don't tell the user the answer." + PROMPT


class QuizCreationStrategy(UnderstandingStrategy):
    def assess(self, topic: str) -> str:
        return f"Your goal is to see if I have understood the topic: {topic}. Your strategy is to have me create a quiz about the topic. You are an educational consultant, and you will guide me in creating meaningful questions that demonstrate deep understanding. Then, you'll have me answer some of these questions. Stay in character and don't tell the user the answer." + PROMPT


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
        strategies = ["Teach-Me", "Quiz", "Oral-Exam", "Debate", "Life-Connection", "Quiz-Creation"]

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
                while True:
                    try:
                        message: Message = await asyncio.wait_for(messages.get(), timeout)
                    except asyncio.TimeoutError:
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
        except Exception as e:
            await self._send_message(thread_id, f'An error occurred: {str(e)}')
            raise

    def _determine_strategy(self, strategy: str) -> str:
        """Prepares the strategy we wish to use and returns the instance."""
        match strategy:
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
                print("Unknown strategy.")
                raise ValueError(f"Unknown strategy: {strategy}")

        return strategy

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