import asyncio
from typing import Callable
import discord
from quest import queue, step

def wrap_steps(obj):
    for field in dir(obj):
        if field.startswith('_'):
            continue

        if callable(method := getattr(obj, field)):
            method = step(method)
            setattr(obj, field, method)

    return obj

class FeedbackWorkflow:
    def __init__(self, metrics_handler, post_event_function, message_handler):
        self._metrics_handler = wrap_steps(metrics_handler)
        self.post_event = post_event_function
        self._send_message = step(message_handler.send_message)

    async def request_feedback(self, guild_id: int, thread_id: int, user_id: int):
        async with queue("feedback", str(thread_id)) as feedback_queue:

            feedback_view = FeedbackView(self.post_event, self._send_message, thread_id)
            message_content = f"<@{user_id}>, on a scale of 1 to 5, how helpful was this conversation?"

            await self._send_message(channel_id=thread_id, message=message_content, view=feedback_view)
            try:
                feedback_score = await asyncio.wait_for(feedback_queue.get(), timeout=300)
                await self._send_message(thread_id, f'Thank you for your feedback: {feedback_score}!')
                await self._metrics_handler.record_feedback(guild_id, thread_id, user_id, feedback_score)
            except asyncio.TimeoutError:
                await self._send_message(thread_id, 'Feedback time out.')

class FeedbackButton(discord.ui.Button):
    def __init__(self, label, thread_id, post_event, _send_message):
        super().__init__(label=label, style=discord.ButtonStyle.grey)
        self.post_event = post_event
        self._send_message = _send_message
        self.thread_id = thread_id

    async def callback(self, interaction: discord.Interaction): # Needs interaction for the function callback to work even if it is not used
        feedback_score = self.label

        await self.post_event(str(self.thread_id), "feedback", str(self.thread_id), "put", feedback_score)
        self.view.stop() # Stop the button interaction after getting one interaction

        await interaction.response.defer(ephemeral=True) # Wait few seconds after getting the feedback to prevent interaction failed error

class FeedbackView(discord.ui.View):
    def __init__(self, post_event, _send_message, thread_id):
        super().__init__()
        self.post_event = post_event
        self._send_message = _send_message
        self.thread_id = thread_id

        # Add FeedbackButton instances to the view
        for i in range(1, 6):
            self.add_item(FeedbackButton(label=str(i), thread_id = self.thread_id, post_event = self.post_event, _send_message = self._send_message))