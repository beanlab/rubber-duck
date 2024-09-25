import asyncio

import discord
from quest import queue, step



class FeedbackWorkflow:
    def __init__(self, feedback_channel_id: int, send_message, record_feedback, ta_channel_object = None):
        self._feedback_channel_id = feedback_channel_id
        self._send_message = step(send_message)
        self._record_feedback = step(record_feedback)
        self._ta_channel_object = ta_channel_object
        self._reactions = {
            '1️⃣': 1,
            '2️⃣': 2,
            '3️⃣': 3,
            '4️⃣': 4,
            '5️⃣': 5
        }

    async def ta_feedback(self, guild_id: int, thread_id: int, user_id: int):
        """
        Takes thread_id, sends it to the ta-channel, collect's feedback
        """
        async with queue("feedback", None) as feedback_queue:
            message_content = f"<@{user_id}>, on a scale of 1 to 5, how helpful was this conversation https://discord.com/channels/{guild_id}/{thread_id}/{user_id} (Add your reaction below)"

            #check to see if this a discord.message
            message_id = await self._send_message(self._feedback_channel_id, message_content)
            # feedback_channel = self.discord_client.get_channel(self._feedback_channel_id)
            feedback_message = await self._ta_channel_object.fetch_message(message_id)

            for reaction in self._reactions:
                await feedback_message.add_reaction(reaction)
                await asyncio.sleep(0.5)


            try:
                feedback_emoji = await asyncio.wait_for(feedback_queue.get(), timeout=60 * 60 * 24 * 7)
                feedback_score = self._reactions[feedback_emoji]
                await self._send_message(thread_id, f'Thank you for your feedback!')

            except asyncio.TimeoutError:
                await self._send_message(thread_id, '*Feedback time out.*')
                feedback_score = 'na'

            # TODO - put a timeout on here. Maybe a week?

            # Record score
            await self._record_feedback(guild_id, thread_id, user_id, feedback_score)

            # Done

    __call__ = ta_feedback