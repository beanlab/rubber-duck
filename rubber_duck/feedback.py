import asyncio
from typing import TypedDict

import discord
from quest import queue, step, alias


class FeedbackConfig(TypedDict):
    channel_id: int
    reviewer_role_id: int


class FeedbackWorkflow:
    def __init__(self,
                 send_message,
                 fetch_message,
                 record_feedback
                 ):
        self._send_message = step(send_message)
        self._fetch_message = fetch_message
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

    async def ta_feedback(self, guild_id, thread_id, user_id, feedback_config: FeedbackConfig):
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

        # TODO - when quest code-object support is implemented, use that to directly return a message object from _send_message
        feedback_channel_id = feedback_config['channel_id']
        review_message_id = await self._send_message(feedback_channel_id, review_message_content)
        review_message = await self._fetch_message(feedback_channel_id, review_message_id)
        feedback_message_id = await self._send_message(thread_id, feedback_message_content)
        feedback_message = await self._fetch_message(thread_id, feedback_message_id)

        async with alias(str(feedback_message_id)), queue("feedback", None) as feedback_queue:
            for reaction in self._reactions:
                await feedback_message.add_reaction(reaction)
                await asyncio.sleep(0.5)  # per discord policy, we wait

            try:
                feedback_emoji, reviewer_id = await self.get_reviewer_feedback(user_id, feedback_queue)
                feedback_score = self._reactions[feedback_emoji]
                await feedback_message.add_reaction('✅')
                await review_message.add_reaction('✅')

            except asyncio.TimeoutError:
                await review_message.add_reaction('❌')
                feedback_score = 'nan'
                reviewer_id = 'nan'

            # Record score

            await self._record_feedback(guild_id, thread_id, user_id, feedback_score, reviewer_id)

            # Done

    #gets reviewer feedback and checks that feedback came from someone other than the student
    async def get_reviewer_feedback(self, user_id, feedback_queue):
        while True:
            #gets feedback
            feedback_emoji, reviewer_id = await asyncio.wait_for(
                feedback_queue.get(),
                timeout=60 * 60 * 24 * 7
            )
            #verifies feedback came from someone other than the student
            if reviewer_id != user_id:
                break

        return feedback_emoji, reviewer_id
