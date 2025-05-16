import asyncio

import discord
from discord import Guild
from quest import step, queue, alias

from ..utils.email_confirmation import EmailConfirmation
from ..utils.logger import duck_logger
from ..utils.protocols import Message
from ..views.registration_views import RegistrationView, RoleSelectionView, EmailConfirmationView

welcome_message = "Hello, welcome to the registration process! Please click the button below to begin."
confirm_message = "We sent a code to your BYU email.\nEnter the code below and click Submit, or click Resend to get a new code."
failed_email_message = 'Unable to validate your email. Please talk to a TA or your instructor.'


class RegistrationWorkflow:
    def __init__(self,
                 send_message,
                 get_channel,
                 fetch_guild
                 ):
        self._send_message = step(send_message)
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self._email_confirmation = None

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):
        # Start the registration process
        author_name, server_id, net_id = await self._set_up(initial_message, settings, thread_id)

        # Get and verify the email
        if not await self._confirm_registration_via_email(net_id,thread_id):
            await self._send_message(thread_id, failed_email_message)
            return

        # Assign Discord roles
        await self._assign_roles(server_id, thread_id, initial_message['author_id'])

    @step
    async def _set_up(self, initial_message, settings, thread_id):
        try:
            author_name = initial_message['author_name']
            server_id = initial_message['guild_id']
                
            self._email_confirmation = EmailConfirmation(settings['sender_email'])
            
            # Create and send the registration view
            view = RegistrationView()
            await self._send_message(thread_id, welcome_message, view=view)
            
            # Wait for the view to be completed
            await view.wait()
            
            if not view.net_id:
                await self._send_message(thread_id, "Registration failed: No Net ID provided. Please start over.")
                raise ValueError("No Net ID provided")
            
            return author_name, server_id, view.net_id
            
        except Exception as e:
            duck_logger.error(f"Setup failed: {e}")
            await self._send_message(thread_id, "Registration setup failed. Please contact an administrator.")
            raise

    @step
    async def _confirm_registration_via_email(self, net_id, thread_id):
        email = f'{net_id}@byu.edu'  # You might want to collect the email address first
        token = self._email_confirmation.prepare_email(email)
        if not token:
            return False

        max_attempts = 3
        attempts = 0
        
        while attempts < max_attempts:
            view = EmailConfirmationView()
            await self._send_message(thread_id, confirm_message, view=view)
            
            # Wait for the view to be completed
            await view.wait()
            
            if hasattr(view, 'resend') and view.resend:
                token = self._email_confirmation.prepare_email(email)
                if not token:
                    return False
                continue
                
            if view.confirmation_code == token:
                await self._send_message(thread_id, "Successfully verified your email!")
                return True
            else:
                attempts += 1
                duck_logger.error(f"Token mismatch: {view.confirmation_code} != {token}")
                if attempts < max_attempts:
                    await self._send_message(thread_id, f"Invalid token. Please try again. ({attempts}/{max_attempts})")
                else:
                    await self._send_message(thread_id, "Too many invalid attempts. Please exit the thread and start again.")
                    return False

        return False

    @step
    async def _get_guild_roles(self, server_id: str, thread_id: int, user_id: int) -> tuple[list[dict], list[int]]:
        """Gets available guild roles and handles role selection"""
        try:
            # Get Discord guild
            guild: Guild = await self._get_guild(server_id)
            if not guild:
                duck_logger.error(f"Could not find Discord server with ID {server_id}")
                await self._send_message(thread_id, "Error: Could not find Discord server.")
                return [], []

            # Get the member
            member = await guild.fetch_member(user_id)
            if not member:
                duck_logger.error(f"Could not find member with ID {user_id} in server {server_id}")
                await self._send_message(thread_id, "Error: Could not find your Discord account in the server.")
                return [], []

            # Get available roles (excluding @everyone and managed roles)
            available_roles = [
                {"id": role.id, "name": role.name}
                for role in await guild.fetch_roles()
                if role.name != "@everyone" and not role.managed
            ]

            # Create and show role selection view
            view = RoleSelectionView(available_roles, guild, member)
            await self._send_message(
                thread_id,
                "Please select the roles you need. You can select multiple roles.",
                view=view
            )

            # Wait for role selection
            await view.wait()

            if not view.selected_roles:
                await self._send_message(thread_id, "No roles selected. Please try again.")
                return [], []

            return available_roles, view.selected_roles

        except Exception as e:
            duck_logger.error(f"Error getting guild roles: {str(e)}")
            await self._send_message(thread_id, "Error getting available roles. Please contact an administrator.")
            return [], []

    @step
    async def _assign_roles(self, server_id: str, thread_id: int, user_id: int):
        """Assigns the selected Discord roles to the user"""
        try:
            # Get roles and selection
            available_roles, selected_role_ids = await self._get_guild_roles(server_id, thread_id, user_id)
            
            if not available_roles or not selected_role_ids:
                return

            # Role assignment is now handled in the RoleSelectionView
            # This function is kept for backward compatibility and logging
            duck_logger.info(f"Roles assigned successfully for user {user_id}")

        except Exception as e:
            duck_logger.error(f"Error in role assignment process: {str(e)}")
            await self._send_message(thread_id, "Error in role assignment process. Please contact an administrator.")
