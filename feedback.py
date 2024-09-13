import asyncio

import discord
from quest import queue, step

CHANNEL_ID = 1284224818698260490


class FeedbackWorkflow:
    def __init__(self, record_feedback, post_event_function, send_message):
        self._record_feedback = step(record_feedback)
        self.post_event = post_event_function
        self._send_message = step(send_message)

    async def request_feedback(self, guild_id: int, thread_id: int, user_id: int):
        async with queue("feedback", str(thread_id)) as feedback_queue:
            async def post_score(score):
                await self.post_event(str(thread_id), "feedback", str(thread_id), "put", score)

            feedback_view = FeedbackView(post_score)
            message_content = f"<@{user_id}>, on a scale of 1 to 5, how helpful was this conversation?"
            await self._send_message(channel_id=thread_id, message=message_content, view=feedback_view)

            try:
                feedback_score = await asyncio.wait_for(feedback_queue.get(), timeout=60 * 30)
                await self._send_message(thread_id, f'Thank you for your feedback!')

            except asyncio.TimeoutError:
                await self._send_message(thread_id, '*Feedback time out.*')
                feedback_score = 'na'

            await self._record_feedback(guild_id, thread_id, user_id, feedback_score)

    async def ta_feedback(self, guild_id: int, thread_id: int, user_id: int):
        """
        Takes thread_id, sends it to the ta-channel, collect's feedback
        """
        async with queue("feedback", str(thread_id)) as feedback_queue:
            async def post_score(score):
                await self.post_event(str(thread_id), "feedback", str(thread_id), "put", score)

            feedback_view = FeedbackView(post_score)
            message_content = (f"Thread ID {thread_id} has finished their conversation\n"
                               f"On a scale of 1 to 5, how helpful was their conversation?")
            await self._send_message(channel_id=CHANNEL_ID, message=message_content, view=feedback_view)

            try:
                feedback_score = await asyncio.wait_for(feedback_queue.get(), timeout=60)
                await self._send_message(thread_id, f'Thank you for your feedback!')

            except asyncio.TimeoutError:
                await self._send_message(thread_id, '*Feedback time out.*')
                feedback_score = 'na'

            await self._record_feedback(guild_id, thread_id, CHANNEL_ID, feedback_score)

class FeedbackButton(discord.ui.Button):
    def __init__(self, label, post_score):
        super().__init__(label=label, style=discord.ButtonStyle.grey)
        self.post_score = post_score

    async def callback(self, interaction: discord.Interaction):
        for button in self.view.children:
            button.disabled = True
        self.view.stop()
        await interaction.response.edit_message(view=self.view)

        # Last thing is to post the feedback, which closes the thread
        feedback_score = self.label
        await self.post_score(feedback_score)


class FeedbackView(discord.ui.View):
    def __init__(self, post_score):
        super().__init__()
        self.post_score = post_score

        # Add FeedbackButton instances to the view
        for i in range(1, 6):
            self.add_item(FeedbackButton(label=str(i), post_score=self.post_score))
