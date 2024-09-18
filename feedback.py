import asyncio

import discord
from quest import queue, step

CHANNEL_ID = 1284224818698260490  # Don't hard code anything. Put this in config.


class FeedbackWorkflow:
    def __init__(self, feedback_channel_id: int, send_message, record_feedback):
        self._feedback_channel_id = feedback_channel_id
        self._send_message = step(send_message)
        self._record_feedback = step(record_feedback)

        self._reactions = {
            '1': 1,
            '2': 2
        }

    async def ta_feedback(self, guild_id: int, thread_id: int, user_id: int):
        """
        Takes thread_id, sends it to the ta-channel, collect's feedback
        """
        async with queue("feedback", None) as feedback_queue:

            feedback_message = self._send_message(self._feedback_channel_id, 'Get feedback')
            for reaction in self._reactions:
                feedback_message.add_reaction(reaction)

            reaction = await feedback_queue.get()

            feedback_score = self._reactions[reaction]

            # TODO - put a timeout on here. Maybe a week?

            # Record score
            await self._record_feedback(guild_id, thread_id, user_id, feedback_score)

            # Done

    __call__ = ta_feedback