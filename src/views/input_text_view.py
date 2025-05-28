from discord.ui import Modal, TextInput, View, Button
from discord import TextStyle
import asyncio
import discord

class InputTextModel(View):
    def __init__(self):
        super().__init__(timeout=300)
        self.future = asyncio.Future()
        
        # Add button to open modal
        self.button = Button(label="Enter Topic", style=discord.ButtonStyle.primary)
        self.button.callback = self.button_callback
        self.add_item(self.button)

    async def button_callback(self, interaction):
        # Create and show the modal
        modal = TopicInputModal(self.future)
        await interaction.response.send_modal(modal)
        
        try:
            # Wait for the modal submission
            topic = await self.future
            # Remove the button and update message
            self.remove_item(self.button)
            await interaction.message.edit(
                content=f"{interaction.message.content}\nSelected: {topic}",
                view=self
            )
        except Exception as e:
            print(f"Error in button callback: {e}")

    async def wait(self):
        """Wait for the modal submission and return the value."""
        try:
            return await asyncio.wait_for(self.future, timeout=300)
        except asyncio.TimeoutError:
            if not self.future.done():
                self.future.set_exception(TimeoutError("Modal submission timed out"))
            raise


class TopicInputModal(Modal):
    def __init__(self, future: asyncio.Future):
        super().__init__(title="Confirm Topic Understanding")
        self.future = future

        # Add TextInput to modal
        self.topic_input = TextInput(
            label="What topic do you want to test?",
            placeholder="Type your topic here",
            style=TextStyle.short,
            required=True
        )
        self.add_item(self.topic_input)

    async def on_submit(self, interaction):
        try:
            value = self.topic_input.value.strip()
            if not value:
                await interaction.response.send_message("Please enter a topic.", ephemeral=True)
                return
            
            await interaction.response.defer()
            if not self.future.done():
                self.future.set_result(value)
        except Exception as e:
            print(f"Error in modal submission: {e}")
            if not self.future.done():
                self.future.set_exception(e)
