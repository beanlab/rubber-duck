import discord
from discord.ui import View, Select
import asyncio
from typing import List


class GeneralSelectionView(View):
    """
    A simple selection view that displays a list of options and allows users to select one.
    """

    def __init__(
        self,
        options: List[str],
        placeholder: str = "Select an option",
        timeout: int = 300
    ):
        super().__init__(timeout=timeout)
        self.future = asyncio.Future()

        # Create a select menu for options
        select = Select(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=option,
                    value=option
                ) for option in options
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle the selection of an option."""
        try:
            selected_value = interaction.data["values"][0]
            await interaction.response.edit_message(
                content=f"{interaction.message.content}\nSelected: {selected_value}",
                view=None
            )
            if not self.future.done():
                self.future.set_result(selected_value)
        except Exception as e:
            print(f"Error in select callback: {e}")
            await interaction.response.send_message(
                "Error processing selection. Please try again.",
                ephemeral=True
            )

    async def wait_for_selection(self) -> str:
        """Wait for the user to select an option."""
        try:
            return await asyncio.wait_for(self.future, timeout=self.timeout)
        except asyncio.TimeoutError:
            if not self.future.done():
                self.future.set_exception(TimeoutError("Selection timed out"))
            raise 