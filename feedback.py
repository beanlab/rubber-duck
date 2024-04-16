import asyncio
from typing import Callable
import discord
from quest import queue, step

# TODO -> Once Quest provides it use that instead

class FeedbackWorkflow:
    def __init__(self, record_feedback, post_event_function, send_message):
        self._record_feedback = step(record_feedback)
        self.post_event = post_event_function
        self._send_message = step(send_message)

    async def request_feedback(self, guild_id: int, thread_id: int, user_id: int):
        async with queue("feedback", str(thread_id)) as feedback_queue:

            feedback_view = FeedbackView(self.post_score, thread_id)
            message_content = f"<@{user_id}>, on a scale of 1 to 5, how helpful was this conversation?"

            await self._send_message(channel_id=thread_id, message=message_content, view=feedback_view)
            try:
                feedback_score = await asyncio.wait_for(feedback_queue.get(), timeout=300)
                await self._send_message(thread_id, f'Thank you for your feedback!')
                await self._record_feedback(guild_id, thread_id, user_id, feedback_score)
            except asyncio.TimeoutError:
                await self._send_message(thread_id, 'Feedback time out.')
    
    async def post_score(self, thread_id: int, score: str):
        await self.post_event(str(thread_id), "feedback", str(thread_id), "put", score)

class FeedbackButton(discord.ui.Button):
    def __init__(self, label, thread_id, post_score):
        super().__init__(label=label, style=discord.ButtonStyle.grey)
        self.post_score = post_score
        self.thread_id = thread_id

    async def callback(self, interaction: discord.Interaction): # Needs interaction for the function callback to work even if it is not used
        feedback_score = self.label

        await self.post_score(self.thread_id, feedback_score)
        self.view.stop() # Stop the button interaction after getting one interaction

        await interaction.response.defer(ephemeral=True) # Wait few seconds after getting the feedback to prevent interaction failed error

class FeedbackView(discord.ui.View):
    def __init__(self, post_score, thread_id):
        super().__init__()
        self.post_score = post_score
        self.thread_id = thread_id

        # Add FeedbackButton instances to the view
        for i in range(1, 6):
            self.add_item(FeedbackButton(label=str(i), thread_id = self.thread_id, post_score = self.post_score))