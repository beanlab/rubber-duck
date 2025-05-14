import asyncio
from typing import Protocol, TypedDict

from quest import step, alias, queue, wrap_steps

from .feedback_manager import FeedbackManager
from ..utils.protocols import AddReaction, SendMessage, ReportError, Message


class RecordFeedback(Protocol):
    async def __call__(self,
                       workflow_type: str, guild_id: int, parent_channel_id: int,
                       thread_id: int, user_id: int, reviewer_id: int,
                       feedback_score: int): ...


class ConversationReviewSettings(TypedDict):
    target_channel_ids: list[int]
    timeout: int


class HaveTAGradingConversation:
    def __init__(self,
                 feedback_manager: FeedbackManager,
                 record_feedback: RecordFeedback,
                 send_message: SendMessage,
                 add_reaction: AddReaction,
                 report_error: ReportError,
                 ):
        self._feedback_manager = wrap_steps(feedback_manager, ['get_conversation'])

        self._record_feedback: RecordFeedback = step(record_feedback)

        self._send_message = step(send_message)
        self._add_reaction = step(add_reaction)
        self._report_error = step(report_error)

        self._reactions = {
            '⏭️': 'nan',
            '1️⃣': 1,
            '2️⃣': 2,
            '3️⃣': 3,
            '4️⃣': 4,
            '5️⃣': 5
        }

    async def _flush_conversations_for_channel(self, thread_id, target_channel_id, timeout):
        while (data := self._feedback_manager.get_conversation(target_channel_id)) is not None:

            student_convo_link = f"<#{data['conversation_thread_id']}>"
            ta_convo_link = f"<#{thread_id}>"

            message_id = await self._send_message(thread_id, "Student Conversation: " + student_convo_link)
            await self._send_message(data['conversation_thread_id'], "Back to Grading: " + ta_convo_link)

            # Add emojis to message
            async with alias(str(message_id)), queue("feedback", None) as feedback_queue:
                for reaction in self._reactions:
                    await self._add_reaction(thread_id, message_id, reaction)

                try:
                    feedback_emoji, reviewer_id = await asyncio.wait_for(
                        feedback_queue.get(),
                        timeout=timeout
                    )
                    feedback_score = self._reactions.get(feedback_emoji, 'nan')
                    await self._add_reaction(thread_id, message_id, '✅')

                    await self._record_feedback(
                        data['duck_type'],
                        data['guild_id'],
                        data['parent_channel_id'],
                        data['conversation_thread_id'],
                        data['user_id'],
                        reviewer_id,
                        feedback_score
                    )

                except asyncio.TimeoutError:
                    self._feedback_manager.remember_conversation(data)
                    await self._add_reaction(thread_id, message_id, '❌')
                    raise

    async def _serve_messages(self, thread_id, settings: ConversationReviewSettings):
        target_channel_ids = settings['target_channel_ids']

        for target_channel_id in target_channel_ids:
            await self._flush_conversations_for_channel(thread_id, target_channel_id, settings.get('timeout', 60 * 5))

        await self._send_message(thread_id, "No more conversations to review.")

    async def __call__(self, thread_id: int, settings: ConversationReviewSettings, initial_message: Message):

        await self._send_message(
            thread_id,
            'After you provide feedback on a conversation, another will be served.\n'
            'If you leave the queue after five minutes, this session will end.\n'
        )

        try:
            await self._serve_messages(thread_id, settings)

        except asyncio.TimeoutError:
            await self._send_message(thread_id, "*This conversation has timed out.*")
