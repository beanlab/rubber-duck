import asyncio
from typing import Callable, NotRequired, TypedDict

from quest import alias, queue, step, wrap_steps

from ...duck_protocols import (
    DuckContext,
    DuckConversation,
    MessageHandler,
    MetricsHandler,
)
from ...gen_ai.ai_responses import ResponsesAPI
from ...metrics.feedback_manager import FeedbackData, FeedbackManager
from ...utils.config_types import CHANNEL_ID
from ...utils.logger import duck_logger
from ...utils.protocols import AddReaction, Message, SendMessage
from ...utils.python_exec_container import PythonExecContainer


class ConversationReviewSettings(TypedDict):
    target_channel_ids: list[CHANNEL_ID]
    timeout: NotRequired[int]


class ConversationReviewWorkflow:
    commands = []
    tool_caches = []

    def __init__(
        self,
        name: str,
        settings: ConversationReviewSettings,
        feedback_manager: FeedbackManager,
        record_feedback: Callable,
        send_message: SendMessage,
        add_reaction: AddReaction,
    ):
        self.name = name
        self._settings = settings
        self._feedback_manager = wrap_steps(
            feedback_manager, ["get_conversation"])
        self._record_feedback = step(record_feedback)
        self._send_message = step(send_message)
        self._add_reaction = step(add_reaction)
        self._reactions = {
            "⏭️": "nan",
            "1️⃣": 1,
            "2️⃣": 2,
            "3️⃣": 3,
            "4️⃣": 4,
            "5️⃣": 5,
        }

    async def _send_review_prompt(
        self,
        review_thread_id: int,
        data: FeedbackData,
    ) -> int:
        conversation_id = data.get("conversation_id")
        if conversation_id is None:
            student_link = f"<#{data['conversation_thread_id']}>"
        else:
            message_channel_id = (
                data["conversation_thread_id"]
                if data.get("conversation_id_is_thread_message")
                else data["parent_channel_id"]
            )
            start_link = (
                "https://discord.com/channels/"
                f"{data['guild_id']}/{message_channel_id}/{conversation_id}"
            )
            student_link = f"[open conversation at its start]({start_link})"

        review_message_id = await self._send_message(
            review_thread_id,
            f"Student conversation: {student_link}",
        )

        return review_message_id

    async def _collect_rating(
        self,
        review_thread_id: int,
        review_message_id: int,
        data: FeedbackData,
        timeout: int,
    ) -> tuple[int | str, int]:
        try:
            async with alias(str(review_message_id)), queue("feedback", None) as feedback_queue:
                for reaction in self._reactions:
                    await self._add_reaction(
                        review_thread_id,
                        review_message_id,
                        reaction,
                    )

                feedback_emoji, reviewer_id = await asyncio.wait_for(
                    feedback_queue.get(),
                    timeout=timeout,
                )
                feedback_score = self._reactions.get(feedback_emoji, "nan")
                await self._add_reaction(
                    review_thread_id,
                    review_message_id,
                    "✅",
                )
                return feedback_score, reviewer_id
        except asyncio.TimeoutError:
            duck_logger.info(f"Feedback timeout for conversation {data}")
            self._feedback_manager.remember_conversation(data)
            await self._add_reaction(
                review_thread_id,
                review_message_id,
                "❌",
            )
            raise

    async def _collect_written_feedback(
        self,
        review_thread_id: int,
        feedback_score: int | str,
    ) -> str:
        if feedback_score == "nan":
            return "-"

        await self._send_message(
            review_thread_id,
            f"Please explain why you gave this conversation a score of {feedback_score}",
        )
        try:
            # Listen on the reviewer-thread alias, not the reaction alias.
            async with queue("messages", None) as messages:
                message: Message = await asyncio.wait_for(
                    messages.get(),
                    timeout=90,
                )
            message_content = message["content"]
            if message_content == "-":
                await self._send_message(
                    review_thread_id,
                    "No feedback provided, skipping.",
                )
            else:
                await self._send_message(
                    review_thread_id,
                    "Feedback recorded, thank you.",
                )
            return message_content
        except asyncio.TimeoutError:
            await self._send_message(
                review_thread_id,
                "No feedback provided, skipping.",
            )
            return "-"

    async def _record_review(
        self,
        data: FeedbackData,
        reviewer_id: int,
        feedback_score: int | str,
        message_content: str,
    ) -> None:
        conversation_id = data.get("conversation_id")
        duck_logger.info(
            f"Recording feedback: {feedback_score} from reviewer {reviewer_id}"
        )
        await self._record_feedback(
            data["duck_type"],
            data["guild_id"],
            data["parent_channel_id"],
            conversation_id
            if conversation_id is not None
            else data["conversation_thread_id"],
            data["user_id"],
            reviewer_id,
            feedback_score,
            message_content,
        )

    async def _flush_conversations_for_channel(
        self,
        review_thread_id: int,
        target_channel_id: int,
        timeout: int,
    ) -> None:
        duck_logger.info(
            f"Flushing conversations for channel {target_channel_id}")
        while (
            data := await self._feedback_manager.get_conversation(target_channel_id)
        ) is not None:
            duck_logger.info(f"Processing conversation: {data}")
            review_message_id = await self._send_review_prompt(review_thread_id, data)
            feedback_score, reviewer_id = await self._collect_rating(
                review_thread_id,
                review_message_id,
                data,
                timeout,
            )
            message_content = await self._collect_written_feedback(
                review_thread_id,
                feedback_score,
            )
            await self._record_review(
                data,
                reviewer_id,
                feedback_score,
                message_content,
            )

    async def _serve_messages(self, review_thread_id: int, timeout: int) -> None:
        target_channel_ids = self._settings["target_channel_ids"]
        duck_logger.info(
            f"Serving messages for channels: {target_channel_ids}")

        for target_channel_id in target_channel_ids:
            await self._flush_conversations_for_channel(
                review_thread_id,
                target_channel_id,
                timeout,
            )

        await self._send_message(review_thread_id, "No more conversations to review.")

    async def __call__(self, context: DuckContext) -> None:
        review_thread_id = context.thread_id
        duck_logger.info(
            f"Starting TA review session in thread {review_thread_id}")
        await self._send_message(
            review_thread_id,
            "After you provide feedback on a conversation, another will be served.\n"
            "**You can skip giving written feedback by clicking \"-\" then \"enter\".**\n"
            "If you do not respond for five minutes, this session will end.\n",
        )

        try:
            await self._serve_messages(review_thread_id, context.timeout)
        except asyncio.TimeoutError:
            duck_logger.info(
                f"TA review session timed out in thread {review_thread_id}")
            await self._send_message(
                review_thread_id,
                "*This conversation has timed out.*",
            )


def build(
    name: str,
    settings: ConversationReviewSettings,
    *,
    message_handler: MessageHandler,
    metrics_handler: MetricsHandler,
    responses_api: ResponsesAPI,
    containers: dict[str, PythonExecContainer],
    sql_session,
    tool_configs: dict,
    feedback_manager: FeedbackManager | None = None,
) -> DuckConversation:
    del responses_api, containers, sql_session, tool_configs
    if feedback_manager is None:
        raise ValueError(
            "The conversation review duck requires a FeedbackManager")

    return ConversationReviewWorkflow(
        name=name,
        settings=settings,
        feedback_manager=feedback_manager,
        record_feedback=metrics_handler.record_feedback,
        send_message=message_handler.send_text,
        add_reaction=message_handler.add_reaction,
    )
