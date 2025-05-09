import asyncio
from typing import Protocol, TypedDict

from quest import step, alias, queue

from .feedback_manager import FeedbackManager
from ..conversation.conversation import generate_error_message
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
        self._feedback_manager = feedback_manager

        self._record_feedback: RecordFeedback = step(record_feedback)

        self._send_message = step(send_message)
        self._add_reaction = step(add_reaction)
        self._report_error = step(report_error)

        self._reactions = {
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
                    await asyncio.sleep(0.5)  # per discord policy, we wait

                try:
                    feedback_emoji, reviewer_id = await asyncio.wait_for(
                        feedback_queue.get(),
                        timeout=timeout
                    )
                    feedback_score = self._reactions[feedback_emoji]
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

    async def _serve_next_message(self, thread_id, settings: ConversationReviewSettings):
        target_channel_ids = settings['target_channel_ids']

        for target_channel_id in target_channel_ids:
            await self._flush_conversations_for_channel(thread_id, target_channel_id, settings.get('timeout', 60 * 5))

        await self._send_message(thread_id, "No more conversations to review.")

    async def __call__(self, thread_id: int, settings: ConversationReviewSettings, initial_message: Message):

        timeout = settings["timeout"]

        async with queue('messages', None) as messages:
            await self._send_message(
                thread_id,
                "Please only use the valid commands listed below.\n"
                "/help (To get more information on how this channel works)\n"
                "/next (To get the next conversation link that requires feedback)\n"
            )

            while True:
                try:
                    message: Message = await asyncio.wait_for(messages.get(), timeout)
                    user_input = message['content'].strip()

                    if user_input.startswith('/'):
                        if user_input == '/help':
                            await self._send_message(thread_id, 'Help message')
                            continue

                        elif user_input == '/next':
                            await self._serve_next_message(thread_id, settings)

                            continue

                        else:
                            await self._send_message(thread_id,
                                                     "Not a valid command. Please use /help or /next.\n")
                            continue

                    else:
                        await self._send_message(thread_id,
                                                 "Please only use the valid commands listed below.\n"
                                                 "/help (To get more information on how this channel works)\n"
                                                 "/next (To get the next conversation link that requires feedback)"
                                                 )

                except asyncio.TimeoutError:
                    await self._send_message(thread_id, "*This conversation has timed out.*")
                    break

                except Exception as ex:
                    error_message, error_code = generate_error_message(message.get('guild_id', 0), thread_id, ex)
                    await self._send_message(thread_id,
                                             f'😵 **Error code {error_code}** 😵\n'
                                             f'An unexpected error occurred. Please contact support.\n'
                                             f'Error code for reference: {error_code}')
                    await self._report_error(error_message)
                    break
