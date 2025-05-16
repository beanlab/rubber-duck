import discord
from discord.ui import View, Button, Select, TextInput, Modal

class NetIDModal(Modal):
    def __init__(self):
        super().__init__(title="Enter Your BYU Net ID")
        self.net_id = None
        
        self.net_id_input = TextInput(
            label="BYU Net ID",
            placeholder="Enter your BYU Net ID (e.g., cosmo123)",
            required=True
        )
        self.add_item(self.net_id_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        self.net_id = self.net_id_input.value.strip().lower()
        await interaction.response.defer()
        self.stop()

class ConfirmationCodeModal(Modal):
    def __init__(self):
        super().__init__(title="Enter Confirmation Code")
        self.code = None
        
        self.code_input = TextInput(
            label="6-Digit Code",
            placeholder="Enter the 6-digit code sent to your email",
            required=True,
            min_length=6,
            max_length=6
        )
        self.add_item(self.code_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        self.code = self.code_input.value.strip()
        await interaction.response.defer()
        self.stop()

class RegistrationView(View):
    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)
        self.net_id = None
        
    @discord.ui.button(label="Start Registration", style=discord.ButtonStyle.primary)
    async def start_registration(self, interaction: discord.Interaction, button: Button):
        # Show the NetID input modal
        modal = NetIDModal()
        await interaction.response.send_modal(modal)
        
        # Wait for the modal to be submitted
        await modal.wait()
        
        if modal.net_id:
            self.net_id = modal.net_id
            # Clear the view and update message
            self.clear_items()
            self.stop()
            try:
                await interaction.message.edit(
                    content="✅ Net ID registration complete!",
                    view=None
                )
            except:
                pass  # Ignore if we can't edit the message
        else:
            await interaction.followup.send("Please enter a valid Net ID to continue.", ephemeral=True)

class EmailConfirmationView(View):
    def __init__(self, timeout=300):
        super().__init__(timeout=timeout)
        self.confirmation_code = None
        self.resend = False
        
    @discord.ui.button(label="Enter Code", style=discord.ButtonStyle.primary)
    async def submit_code(self, interaction: discord.Interaction, button: Button):
        # Show the confirmation code modal
        modal = ConfirmationCodeModal()
        await interaction.response.send_modal(modal)
        
        # Wait for the modal to be submitted
        await modal.wait()
        
        if modal.code:
            self.confirmation_code = modal.code
            # Clear the view and update message
            self.clear_items()
            self.stop()
            try:
                await interaction.message.edit(
                    content="✅ Email confirmation complete!",
                    view=None
                )
            except:
                pass  # Ignore if we can't edit the message
        else:
            await interaction.followup.send("Please enter a valid 6-digit code.", ephemeral=True)
        
    @discord.ui.button(label="Resend Code", style=discord.ButtonStyle.secondary)
    async def resend_code(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        self.resend = True
        # Clear the view and update message
        self.clear_items()
        self.stop()
        try:
            await interaction.message.edit(
                content="🔄 Code resent! Please check your email.",
                view=None
            )
        except:
            pass  # Ignore if we can't edit the message

    async def on_timeout(self):
        # Destroy the view and all its widgets
        self.clear_items()
        self.stop()
        
        # Try to update the message
        try:
            if self.message:
                await self.message.edit(
                    content="⏰ Email confirmation timed out.",
                    view=None
                )
        except:
            pass  # Ignore if we can't edit the message

class RoleSelectionView(View):
    def __init__(self, roles: list[dict], guild: discord.Guild, member: discord.Member, timeout=300):
        super().__init__(timeout=timeout)
        self.selected_roles = []
        self.confirmed = False
        self.guild = guild
        self.member = member
        self.assignment_complete = False
        
        # Create a select menu for roles
        select = Select(
            placeholder="Select your roles",
            min_values=1,
            max_values=min(5, len(roles)),  # Limit to 5 roles max
            options=[
                discord.SelectOption(
                    label=role["name"],
                    value=str(role["id"]),
                    description=f"Select the {role['name']} role"
                ) for role in roles
            ]
        )
        
        select.callback = self.role_select_callback
        self.add_item(select)
        
        # Add a confirm button
        self.add_item(Button(
            label="Confirm Selection",
            style=discord.ButtonStyle.primary,
            custom_id="confirm_roles"
        ))
        
    async def role_select_callback(self, interaction: discord.Interaction):
        try:
            self.selected_roles = [int(value) for value in interaction.data["values"]]
            await interaction.response.send_message(
                f"Selected {len(self.selected_roles)} role(s). Click 'Confirm Selection' when ready.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                "Error processing role selection. Please try again.",
                ephemeral=True
            )
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] == "confirm_roles":
            if not self.selected_roles:
                await interaction.response.send_message(
                    "Please select at least one role first.",
                    ephemeral=True
                )
                return False
                
            if self.confirmed:
                await interaction.response.send_message(
                    "Roles already confirmed. Please wait...",
                    ephemeral=True
                )
                return False
                
            self.confirmed = True
            await interaction.response.send_message(
                "Processing your role selection...",
                ephemeral=True
            )
            
            try:
                # Get the role objects
                selected_roles = []
                for role_id in self.selected_roles:
                    role = self.guild.get_role(role_id)
                    if role:
                        selected_roles.append(role)

                if not selected_roles:
                    await interaction.followup.send(
                        "Error: Could not find the selected roles.",
                        ephemeral=True
                    )
                    return False

                # Assign roles
                await self.member.add_roles(*selected_roles, reason="User registration")
                
                # Send confirmation message
                role_names = ", ".join(role.name for role in selected_roles)
                await interaction.followup.send(
                    f"Successfully assigned you the following roles: {role_names}!",
                    ephemeral=True
                )
                
                self.assignment_complete = True
                
                # Destroy the view and all its widgets
                self.clear_items()
                self.stop()
                
                # Update the message to remove the view and show completion
                try:
                    await interaction.message.edit(
                        content="✅ Role selection complete!",
                        view=None
                    )
                except:
                    pass  # Ignore if we can't edit the message
                
            except Exception as e:
                await interaction.followup.send(
                    "Error assigning roles. Please contact an administrator.",
                    ephemeral=True
                )
                return False
                
            return True
            
        return True
        
    async def on_timeout(self):
        # Destroy the view and all its widgets
        self.clear_items()
        self.stop()
        
        # Try to update the message
        try:
            if self.message:
                await self.message.edit(
                    content="⏰ Role selection timed out.",
                    view=None
                )
        except:
            pass  # Ignore if we can't edit the message 