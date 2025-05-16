import asyncio
import re

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
        await self._assign_roles(server_id, thread_id, initial_message['author_id'], settings)

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
    async def _get_guild_roles(self, thread_id: int, server_id: int, settings: dict) -> tuple[list[dict], list[int]]:
        """Gets available guild roles and handles role selection"""
        try:
            # Get all roles from the guild
            guild = await self._get_guild(server_id)
            if not guild:
                raise ValueError("Guild not found")

            # Get role patterns from config
            role_patterns = settings.get("roles", {}).get("patterns", [])
            if not role_patterns:
                raise ValueError("No role patterns configured")

            # Filter roles based on patterns
            available_roles = []
            for role in guild.roles:
                for pattern_info in role_patterns:
                    if re.match(pattern_info["pattern"], role.name):
                        available_roles.append({
                            "id": role.id,
                            "name": role.name,
                            "description": pattern_info["description"]
                        })
                        break

            if not available_roles:
                await self._send_message(thread_id, "No matching roles found. Please contact an administrator.")
                return [], []

            # Create and show role selection view
            view = RoleSelectionView(available_roles)
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
    async def _assign_roles(self, server_id: str, thread_id: int, user_id: int, settings: dict):
        """Assigns the selected Discord roles to the user"""
        try:
            # Get roles and selection
            available_roles, selected_role_ids = await self._get_guild_roles(thread_id, server_id, settings)
            
            if not available_roles or not selected_role_ids:
                return

            # Get Discord guild and member
            guild: Guild = await self._get_guild(server_id)
            member = await guild.fetch_member(user_id)

            # Get the role objects
            selected_roles = []
            for role_id in selected_role_ids:
                role = guild.get_role(role_id)
                if role:
                    selected_roles.append(role)

            if not selected_roles:
                await self._send_message(thread_id, "Error: Could not find the selected roles.")
                return

            # Assign roles
            await member.add_roles(*selected_roles, reason="User registration")
            
            # Send confirmation message
            role_names = ", ".join(role.name for role in selected_roles)
            await self._send_message(thread_id, f"Successfully assigned you the following roles: {role_names}!")

        except Exception as e:
            duck_logger.error(f"Error in role assignment process: {str(e)}")
            await self._send_message(thread_id, "Error in role assignment process. Please contact an administrator.")
