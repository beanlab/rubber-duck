import asyncio
from typing import TypedDict

from quest import queue, step, alias


class FeedbackConfig(TypedDict):
    channel_id: int
    reviewer_role_id: int
    allow_self_feedback: bool
    feedback_timeout: int


class FeedbackWorkflow:
    def __init__(self,
                 send_message,
                 add_reaction,
                 record_feedback
                 ):
        self._send_message = step(send_message)
        self._add_reaction = step(add_reaction)
        self._record_feedback = record_feedback

        self._reactions = {
            '1️⃣': 1,
            '2️⃣': 2,
            '3️⃣': 3,
            '4️⃣': 4,
            '5️⃣': 5
        }

    async def __call__(self, *args):
        return await self.ta_feedback(*args)

    async def ta_feedback(self, workflow_type, guild_id, thread_id, user_id, feedback_config: FeedbackConfig):
        """
        Takes thread_id, sends it to the ta-channel, collect's feedback
        """

        review_message_content = (
            f"How effective was this conversation: "
            f"https://discord.com/channels/{guild_id}/{thread_id}/{user_id}"
        )
        feedback_message_content = (
            f"On a scale of 1 to 5, "
            f"how effective was this conversation: "
        )

        if 'reviewer_role_id' in feedback_config:
            review_message_content = f"<@{feedback_config['reviewer_role_id']}> {review_message_content}"

        feedback_message_id = await self._send_message(thread_id, feedback_message_content)

        async with alias(str(feedback_message_id)), queue("feedback", None) as feedback_queue:
            for reaction in self._reactions:
                await self._add_reaction(thread_id, feedback_message_id, reaction)
                await asyncio.sleep(0.5)  # per discord policy, we wait

            reviewer_channel_id = feedback_config['channel_id']
            review_message_id = await self._send_message(reviewer_channel_id, review_message_content)

            try:
                feedback_emoji, reviewer_id = await self.get_reviewer_feedback(
                    user_id, feedback_queue,
                    feedback_config.get('allow_self_feedback', False),
                    feedback_config.get('feedback_timeout', 604800)
                )
                feedback_score = self._reactions[feedback_emoji]
                await self._add_reaction(thread_id, feedback_message_id,'✅')
                await self._add_reaction(reviewer_channel_id, review_message_id, '✅')

            except asyncio.TimeoutError:
                await self._add_reaction('❌')
                feedback_score = 'nan'
                reviewer_id = 'nan'

            # Record score

            await self._record_feedback(workflow_type, guild_id, thread_id, user_id, feedback_score, reviewer_id)

            # Done

    async def get_reviewer_feedback(self, user_id, feedback_queue, allow_self_feedback, feedback_timeout):
        while True:
            #Wait for feedback to be given
            feedback_emoji, reviewer_id = await asyncio.wait_for(
                feedback_queue.get(),
                timeout=feedback_timeout
            )
            #Verify that the feedback came from someone other than the student
            if allow_self_feedback or reviewer_id != user_id:
                return feedback_emoji, reviewer_id
