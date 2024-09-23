import asyncio

import discord
from quest import queue, step



class FeedbackWorkflow:
    def __init__(self, feedback_channel_id: int, send_message, record_feedback):
        self._feedback_channel_id = feedback_channel_id
        self._send_message = step(send_message)
        self._record_feedback = step(record_feedback)

        self._reactions = {
            ':one:': 1,
            ':two:': 2,
            ':three:': 3,
            ':four:': 4,
            ':five:': 5
        }

    async def ta_feedback(self, guild_id: int, thread_id: int, user_id: int):
        """
        Takes thread_id, sends it to the ta-channel, collect's feedback
        """
        async with queue("feedback", None) as feedback_queue:
            message_content = f"<@{user_id}>, on a scale of 1 to 5, how helpful was this conversation https://discord.com/channels/{guild_id}/{thread_id}/{user_id} (Add your reaction below)"


            feedback_message_id = await self._send_message(self._feedback_channel_id, message_content)
            # for reaction in self._reactions:
            #     await feedback_message.add_reaction(reaction)


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