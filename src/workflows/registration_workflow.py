import asyncio
import json
import re
import uuid
from typing import Callable

from discord import Guild, utils
from quest import step, queue

from ..utils.config_types import RegistrationSettings, DuckContext
from ..utils.logger import duck_logger
from ..utils.protocols import Message
from ..utils.send_email import EmailSender


class RegistrationWorkflow:
    def __init__(self,
                 name: str,
                 send_message,
                 get_channel,
                 fetch_guild,
                 email_sender: EmailSender,
                 settings: RegistrationSettings,
                 agent_suspicion_tool: Callable | None
                 ):
        self.name = name
        self._send_message = step(send_message)
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self._email_sender = email_sender
        self._settings = settings
        self._suspicion_tool = agent_suspicion_tool

    async def __call__(self, context: DuckContext):
        try:
            # Start the registration process
            thread_id = context.thread_id
            net_id = await self._get_net_id(thread_id, context.timeout)
            if not net_id:
                await self._send_message(thread_id, "Registration failed: No Net ID provided. Please start over.")
                return

            server_id = context.guild_id
            author_id = context.author_id

            # Get and verify the email
            if not await self._confirm_registration_via_email(net_id, thread_id, self._settings['email_domain'],
                                                              context.timeout):
                await self._send_message(thread_id,
                                         'Unable to validate your email. Please talk to a TA or your instructor.')
                return

            # Assign Discord roles
            await self._assign_roles(server_id, thread_id, author_id, self._settings, context.timeout)

            # Get and assign nickname
            await self._nickname_flow(context, server_id, author_id, thread_id)
        except Exception as e:
            await self._send_message(self._settings['ta_channel_id'],
                                     f"Registration workflow failed for user {context.author_id} in server {context.guild_id}.\n"
                                     f"Error: {e}\n"
                                     f"Thread: <#{context.thread_id}>")

    def _generate_token(self):
        code = str(uuid.uuid4().int)[:6]
        return code

    async def _wait_for_message(self, timeout=300) -> str | None:
        async with queue('messages', None) as messages:
            try:
                message: Message = await asyncio.wait_for(messages.get(), timeout)
                return message['content']
            except asyncio.TimeoutError:  # Close the thread if the conversation has closed
                return None

    @step
    async def _get_names(self, thread_id, timeout):
        try:
            await self._send_message(thread_id, "Please enter your preferred first and last name, e.g. 'Shane Reese'")

            # Wait for user response
            name = await self._wait_for_message(timeout)
            return name

        except Exception as e:
            duck_logger.error(f"Setup failed: {e}")
            await self._send_message(thread_id, "Registration setup failed. Please contact an administrator.")
            raise

    @step
    async def _get_net_id(self, thread_id, timeout: int = 300):
        try:
            await self._send_message(thread_id, "Please enter your BYU Net ID to begin the registration process.")

            # Wait for user response
            net_id = await self._wait_for_message(timeout)
            return net_id

        except Exception as e:
            duck_logger.error(f"Setup failed: {e}")
            await self._send_message(thread_id, "Registration setup failed. Please contact an administrator.")
            raise

    @step
    async def _confirm_registration_via_email(self, net_id: str, thread_id, email_domain: str,
                                              timeout: int = 300) -> bool:
        email = f"{net_id}@{email_domain}"
        token = self._generate_token()
        if not self._email_sender.send_email(email, token):
            return False

        max_attempts = 3
        attempts = 0

        while attempts < max_attempts:
            await self._send_message(thread_id,
                                     "Email Verification:\n"
                                     f"We sent a verification code to your BYU email: {email}\n"
                                     "Enter the code in the chat\n"
                                     "or type *resend* to get a new code")

            # Wait for user response
            response = await self._wait_for_message(timeout)
            if not response:
                await self._send_message(thread_id, "No response received. Please start a new chat.")
                return False

            if response.lower() == 'resend':
                token = self._email_sender.send_email(email, token)
                if not token:
                    return False
                continue

            if response == token:
                await self._send_message(thread_id, "Successfully verified your email!")
                return True
            
            else:
                attempts += 1
                if attempts < max_attempts:
                    await self._send_message(thread_id,
                                             f"Unexpected token. Please enter the token again. ({attempts}/{max_attempts})")
                else:
                    await self._send_message(thread_id,
                                             "Too many invalid attempts. Please exit the thread and start again.")
                    return False

        return False

    @step
    async def _select_roles(self, thread_id, available_roles, timeout: int = 300):
        while True:
            # Display available roles
            role_list = "\n".join([f"{i + 1}. {role['name']}"
                                   for i, role in enumerate(available_roles)])
            await self._send_message(thread_id,
                                     "These are the available roles you can select. Please indicate which roles are applicable to you:\n\n"
                                     "- These may include lecture section or lab section\n\n"
                                     "Enter the numbers of your roles separated by commas. Or say 'skip' to skip this step.\n"
                                     "**Example: '1,3,4'**\n\n"
                                     f"Available roles:\n{role_list}")

            # Wait for user response
            response = await self._wait_for_message(timeout)
            if response is None or not response.strip():
                await self._send_message(thread_id, "No response received. No additional roles will be assigned.")
                return []

            if 'skip' in response.lower():
                await self._send_message(thread_id, "Skipping role selection. No additional roles will be assigned.")
                return []

            # Split by comma and convert to integers
            selected_indices = []
            errors = []
            for idx in response.split(','):
                try:
                    num = int(idx.strip())
                    if 1 <= num <= len(available_roles):
                        selected_indices.append(num - 1)
                except ValueError:
                    errors.append(f'"{idx}" is not a valid role number')

            if errors:
                await self._send_message(thread_id, "\n".join(errors))
                continue

            selected_roles = [
                available_roles[idx]['id']
                for idx in selected_indices
            ]

            return selected_roles

    @step
    async def _get_available_roles(
            self, thread_id: int, server_id: int, settings: RegistrationSettings
    ) -> tuple[list[int], int]:
        """Gets available guild roles and the authenticated user role"""
        try:
            # Get all roles from the guild
            guild = await self._get_guild(server_id)
            if not guild:
                raise ValueError(f"Guild {server_id} not found")

            # Get role patterns from config
            role_patterns = settings.get("roles", {}).get("patterns", [])
            if not role_patterns:
                duck_logger.info("No role patterns configured for this server")

            # Filter roles based on patterns
            available_roles = []
            authenticated_user_role_id = None
            for role in guild.roles:
                if role.name == settings['authenticated_user_role_name']:
                    authenticated_user_role_id = role.id
                    continue

                # If no patterns are configured, skip additional role filtering
                for pattern_info in role_patterns:
                    if re.search(pattern_info["pattern"], role.name):
                        available_roles.append({
                            "id": role.id,
                            "name": role.name
                        })

            if authenticated_user_role_id is None:
                raise ValueError('No authenticated_user_role_name configured for this server '
                                 '(or it didn\'t match any existing role names).')

            return available_roles, authenticated_user_role_id

        except Exception as e:
            duck_logger.error(f"Error getting guild roles: {str(e)}")
            await self._send_message(thread_id, "Error getting available roles. Please contact an administrator.")
            raise

    @step
    async def _assign_roles(self, server_id: int, thread_id: int, user_id: int, settings: RegistrationSettings,
                            timeout: int = 300):
        """Gets available roles, lets the user select the relevant ones, and assigns them"""
        try:
            # Get roles and selection
            if settings.get('roles') is None:
                duck_logger.debug("No roles configured for this server. Using authenticated user role only.")
                role_name = settings['authenticated_user_role_name']
                guild: Guild = await self._get_guild(server_id)
                member = await guild.fetch_member(user_id)

                # Find role by name instead of ID
                role = utils.get(guild.roles, name=role_name)  # This function is from the discord.utils module
                if not role:
                    raise ValueError(f"Role '{role_name}' not found in guild '{guild.name}'.")

                selected_roles = [role]
                await member.add_roles(role, reason="User registration")

            else:
                available_roles, authenticated_role_id = await self._get_available_roles(thread_id, server_id, settings)
                if available_roles:
                    selected_role_ids = await self._select_roles(thread_id, available_roles, timeout)
                else:
                    selected_role_ids = []

                selected_role_ids.append(authenticated_role_id)

                # Get Discord guild and member
                guild: Guild = await self._get_guild(server_id)
                member = await guild.fetch_member(user_id)

                # Get the role objects
                selected_roles = []
                for role_id in selected_role_ids:
                    role = guild.get_role(role_id)
                    if role:
                        selected_roles.append(role)

                if not selected_roles:  # sanity check
                    raise ValueError('Could not lookup role objects from the selected role IDs.')

                # Assign roles
                new_roles = [role for role in selected_roles if role not in member.roles]
                if new_roles:
                    await member.add_roles(*new_roles, reason="User registration")

            # Send confirmation message
            role_names = ", ".join(role.name for role in selected_roles)
            await self._send_message(thread_id, f"Successfully gave you the following roles: {role_names}")

        except Exception as e:
            duck_logger.exception(f"Error in role assignment process: {str(e)}")
            await self._send_message(thread_id, "Error in role assignment process. Please contact an administrator.")
            raise

    @step
    async def _is_suspicious(self, context: DuckContext, name: str) -> tuple[bool, str]:
        """Check if a nickname looks suspicious."""

        if len(name) < 3 or len(name) > 64:
            return True, "Name length not typical"
        if any(char.isdigit() for char in name):
            return True, "Contains digits"
        if any(char in "!@#$%^&*()_+=~`[]{};:'\",.<>?/\\|" for char in name):
            return True, "Contains unusual symbols"
        if any(ord(char) > 10000 for char in name):
            return True, "Contains emojis/unicode"

        if self._suspicion_tool:
            try:
                raw = await self._suspicion_tool(context, name)
                result = json.loads(raw)
                return bool(result.get("suspicious", False)), result.get("reason", "No reason provided")
            except Exception as e:
                duck_logger.warning(f"Suspicion tool failed: {e}")

        return False, "Name looks normal"

    @step
    async def _assign_nickname(
            self,
            context: DuckContext,
            server_id: int,
            user_id: int,
            name: str
    ) -> tuple[bool, str]:
        """Try assigning the nickname, return (success, reason)."""
        try:
            guild: Guild = await self._get_guild(server_id)
            member = await guild.fetch_member(user_id)

            suspicious, reason = await self._is_suspicious(context, name)
            if suspicious:
                return False, reason

            if member.guild.owner_id == member.id:
                return False, "Cannot change the server owner's nickname"

            await member.edit(nick=name, reason="Student registration")
            return True, "Nickname set successfully"

        except Exception as e:
            duck_logger.exception(f"Error assigning nickname: {e}")
            return False, "Unexpected error"

    @step
    async def _nickname_flow(
            self,
            context: DuckContext,
            server_id: int,
            author_id: int,
            thread_id: int,
            max_retries: int = 1
    ):
        """Handle full nickname assignment flow with retries and TA escalation."""
        guild: Guild = await self._get_guild(server_id)
        member = await guild.fetch_member(author_id)
        for attempt in range(max_retries + 1):
            name = await self._get_names(thread_id, context.timeout)
            if not name:
                await self._send_message(thread_id, "Registration incomplete: No name provided. Please start over.")
                return

            success, reason = await self._assign_nickname(context, server_id, author_id, name)
            if success:
                await self._send_message(thread_id, f"Your nickname has been set to **{name}**")
                break
            if attempt < max_retries:
                await self._send_message(thread_id, f"Please try again.")
            else:
                await self._send_message(
                    thread_id,
                    "I'm sorry, this is likely my problem, but I couldn’t set your nickname. A TA will need to approve it manually."
                )
                await self._send_message(
                    self._settings['ta_channel_id'],
                    f"Student {member.mention} needs nickname approval.\n"
                    f"Reason: {reason}\n"
                    f"Thread: <#{thread_id}>"
                )
                break
