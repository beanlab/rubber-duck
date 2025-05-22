import discord
from discord.ui import View, Select, Button


class AssignmentSelectionView(View):
    def __init__(self, assignments: list[str], callback, timeout=300):
        super().__init__(timeout=timeout)
        self.callback = callback
        self.selected_assignment = None

        # Create a select menu for assignments
        select = Select(
            placeholder="Select your assignment",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=assignment,
                    value=assignment,
                    description=f"Select {assignment}"
                ) for assignment in assignments
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

        # Add a confirm button
        confirm_button = Button(
            label="Confirm Selection",
            style=discord.ButtonStyle.primary
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)
    
    async def select_callback(self, interaction: discord.Interaction):
        try:
            self.selected_assignment = interaction.data["values"][0]
            await interaction.response.defer()
        except Exception as e:
            print(f"Error in select callback: {e}")
            await interaction.response.send_message(
                "Error processing assignment selection. Please try again.",
                ephemeral=True
            )

    async def confirm_callback(self, interaction: discord.Interaction):
        if not self.selected_assignment:
            await interaction.response.send_message(
                "Please select an assignment first.",
                ephemeral=True
            )
            return

        try:
            await self.callback(self.selected_assignment)
            await interaction.response.defer()
            
            # Update the message to show the selection
            await interaction.message.edit(
                content=f"Selected assignment: {self.selected_assignment}",
                view=None
            )
        except Exception as e:
            print(f"Error in confirm callback: {e}")
            await interaction.response.send_message(
                "There was an error processing your selection. Please try again.",
                ephemeral=True
            ) 