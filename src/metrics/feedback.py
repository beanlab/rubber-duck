import asyncio
from typing import Protocol, TypedDict

from quest import step, alias, queue, wrap_steps

from .feedback_manager import FeedbackManager
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger
from ..utils.protocols import AddReaction, SendMessage, Message


class RecordFeedback(Protocol):
    async def __call__(self,
                       workflow_type: str, guild_id: int, parent_channel_id: int,
                       thread_id: int, user_id: int, reviewer_id: int,
                       feedback_score: int, written_feedback: str): ...


class ConversationReviewSettings(TypedDict):
    target_channel_ids: list[int]
    timeout: int


class HaveTAGradingConversation:
    def __init__(self,
                 name: str,
                 settings: ConversationReviewSettings,
                 feedback_manager: FeedbackManager,
                 record_feedback: RecordFeedback,
                 send_message: SendMessage,
                 add_reaction: AddReaction,
                 ):
        self.name = name

        self._settings = settings

        self._feedback_manager = wrap_steps(feedback_manager, ['get_conversation'])
        self._record_feedback: RecordFeedback = step(record_feedback)
        self._send_message = step(send_message)
        self._add_reaction = step(add_reaction)

        self._reactions = {
            '⏭️': 'nan',
            '1️⃣': 1,
            '2️⃣': 2,
            '3️⃣': 3,
            '4️⃣': 4,
            '5️⃣': 5
        }

    async def _flush_conversations_for_channel(self, thread_id, target_channel_id, timeout):
        duck_logger.info(f"Flushing conversations for channel {target_channel_id}")
        while (data := await self._feedback_manager.get_conversation(target_channel_id)) is not None:
            duck_logger.info(f"Processing conversation: {data}")

            student_convo_link = f"<#{data['conversation_thread_id']}>"
            ta_convo_link = f"<#{thread_id}>"

            message_id = await self._send_message(thread_id, "Student Conversation: " + student_convo_link)
            await self._send_message(data['conversation_thread_id'], "Back to Grading: " + ta_convo_link)

            # Add emojis to message
            async with alias(str(message_id)), queue("feedback", None) as feedback_queue:
                for reaction in self._reactions:
                    await self._add_reaction(thread_id, message_id, reaction)

                try:
                    # TODO - perhaps run the reactions in parallel to the feedback get
                    feedback_emoji, reviewer_id = await asyncio.wait_for(
                        feedback_queue.get(),
                        timeout=timeout
                    )
                    feedback_score = self._reactions.get(feedback_emoji, 'nan')
                    await self._add_reaction(thread_id, message_id, '✅')

                    if feedback_score != 'nan':
                        await self._send_message(thread_id,
                                                 f"Please explain why you gave this conversation a score of {feedback_score}")
                        try:
                            async with queue('messages', None) as messages:
                                message: Message = await asyncio.wait_for(messages.get(), timeout=90)
                                message_content = message['content']
                            if message_content == '-':
                                await self._send_message(thread_id, "No feedback provided, skipping.")
                            else:
                                await self._send_message(thread_id, f"Feedback recorded, thank you.")
                        except asyncio.TimeoutError:
                            message_content = '-'
                            await self._send_message(thread_id, "No feedback provided, skipping.")
                    else:
                        message_content = '-'

                    duck_logger.info(f"Recording feedback: {feedback_score} from reviewer {reviewer_id}")
                    await self._record_feedback(
                        data['duck_type'],
                        data['guild_id'],
                        data['parent_channel_id'],
                        data['conversation_thread_id'],
                        data['user_id'],
                        reviewer_id,
                        feedback_score,
                        message_content
                    )

                except asyncio.TimeoutError:
                    duck_logger.warning(f"Feedback timeout for conversation {data}")
                    self._feedback_manager.remember_conversation(data)
                    await self._add_reaction(thread_id, message_id, '❌')
                    raise

    async def _serve_messages(self, thread_id):
        target_channel_ids = self._settings['target_channel_ids']
        duck_logger.info(f"Serving messages for channels: {target_channel_ids}")

        for target_channel_id in target_channel_ids:
            await self._flush_conversations_for_channel(thread_id, target_channel_id,
                                                        self._settings.get('timeout', 60 * 5))

        await self._send_message(thread_id, "No more conversations to review.")

    async def __call__(self, context: DuckContext):
        thread_id = context.thread_id
        duck_logger.info(f"Starting TA review session in thread {thread_id}")

        await self._send_message(
            thread_id,
            'After you provide feedback on a conversation, another will be served.\n'
            '**You can skip giving written feedback to a conversation by clicking "-" then "enter".**\n'
            'If you do not respond for five minutes, this session will end.\n'
        )

        try:
            await self._serve_messages(thread_id)

        except asyncio.TimeoutError:
            duck_logger.warning(f"TA review session timed out in thread {thread_id}")
            await self._send_message(thread_id, "*This conversation has timed out.*")
