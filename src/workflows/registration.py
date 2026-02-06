import re
import uuid
from dataclasses import dataclass

import discord
from discord import Guild, utils
from quest import step

from ..armory.tools import register_tool
from ..utils.config_types import RegistrationSettings, DuckContext
from ..utils.logger import duck_logger
from ..utils.message_utils import wait_for_message as _wait_for_message
from ..utils.send_email import EmailSender
from ..utils.protocols import ConversationComplete


async def wait_for_message(*args, **kwargs) -> str:
    response = await _wait_for_message(*args, **kwargs)
    if response is None:
        raise ConversationComplete("This conversation has timed out.")
    return response['content']

@dataclass
class RegistrationInfo:
    net_id: str | None
    net_id_checked: bool
    email_verified: bool
    nickname: str | None
    nickname_reason: str | None
    roles_assigned: str | None

class Registration:
    def __init__(self,
                 send_message,
                 get_channel,
                 fetch_guild,
                 email_sender: EmailSender,
                 settings: RegistrationSettings
                 ):
        self._send_message = step(send_message)
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self._email_sender = email_sender
        self._settings = settings

    async def run(self, ctx: DuckContext) -> RegistrationInfo | None:
        # Start the registration process
        registration_info = RegistrationInfo(None, False, False, None, None, None)
        try:
            net_id = await self.get_net_id(ctx)
            if not net_id:
                return registration_info
            registration_info.net_id = net_id

            if not await self.check_net_id(net_id):
                return registration_info
            registration_info.net_id_checked = True

            # Get and verify the email
            if not await self.confirm_registration_via_email(ctx, net_id):
                return registration_info
            registration_info.email_verified = True

            # Get and assign nickname
            name, reason = await self.nickname_flow(ctx)
            if reason:
                registration_info.nickname_reason = reason
                return registration_info
            registration_info.nickname = name

            # Assign Discord roles
            roles = await self.assign_roles(ctx)
            if roles:
                registration_info.roles = roles
            else:
                return registration_info

        except ConversationComplete:
            await self._send_message(ctx.thread_id, "This conversation has timed out.")
        except Exception as e:
            duck_logger.exception(f"Setup failed: {e}")
            await self._send_message(ctx.thread_id, "Registration setup failed. Please contact an administrator.")
            if self._settings.get('ta_channel_id'):
                await self._send_message(
                    self._settings['ta_channel_id'],
                    f"Registration workflow failed. Thread: <#{ctx.thread_id}>"
                )

    @register_tool
    async def check_net_id(self, netid: str):
        if not netid:
            return False

        # Regex: netid (5–8 chars, starts with letter, lowercase letters/numbers only)
        NETID_REGEX = re.compile(r"^[a-z][a-z0-9]{4,7}$")

        return bool(NETID_REGEX.match(netid))


    def _generate_token(self):
        code = str(uuid.uuid4().int)[:6]
        return code

    @step
    async def _get_names(self, thread_id, timeout):
        await self._send_message(thread_id, "Please enter your preferred first and last name, e.g. 'Shane Reese'")

        # Wait for user response
        name = await wait_for_message(timeout)
        return name

    @step
    @register_tool
    async def get_net_id(self, ctx: DuckContext):
        thread_id = ctx.thread_id
        timeout = ctx.timeout or 300
        await self._send_message(thread_id, "Please enter your BYU Net ID to begin the registration process.")

        # Wait for user response
        net_id = await wait_for_message(timeout)
        return net_id

    @step
    @register_tool
    async def confirm_registration_via_email(self, ctx: DuckContext, net_id: str) -> bool:
        thread_id = ctx.thread_id
        timeout = ctx.timeout or 300
        email_domain = self._settings['email_domain']
        email = f"{net_id}@{email_domain}"
        token = self._generate_token()
        if not self._email_sender.send_email(email, token):
            return False

        max_attempts = 3
        attempts = 0

        while attempts < max_attempts:
            await self._send_message(thread_id,
                                     "Email Verification:\n"
                                     f"We sent a verification code to: {email}\n"
                                     "Enter the code in the chat\n"
                                     "or type *resend* to get a new code")

            # Wait for user response
            response = await wait_for_message(timeout)

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
                    await self._send_message(
                        thread_id,
                        f"Unexpected token. Please enter the token again. ({attempts}/{max_attempts})"
                    )
                else:
                    await self._send_message(
                        thread_id,
                        "Too many invalid attempts. Please exit the thread and start again."
                    )
                    return False
        return False

    async def get_user_roles(self, member: discord.Member) -> list[int]:
        roles = [role.id for role in member.roles if role.name != "@everyone"]
        return roles

    @step
    async def _select_roles(self, thread_id, available_roles, timeout: int = 300):
        while True:
            # Display available roles
            role_list = "\n".join([f"{i + 1}. {role['name']}"
                                   for i, role in enumerate(available_roles)])
            await self._send_message(
                thread_id,
                "These are the available roles you can select. Please indicate which roles are applicable to you:\n\n"
                "- These may include lecture section or lab section\n\n"
                "Enter the numbers of your roles separated by commas. Or say 'skip' to skip this step.\n"
                "**Example: '1,3,4'**\n\n"
                f"Available roles:\n{role_list}"
            )

            # Wait for user response
            response = await wait_for_message(timeout)

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

    @step
    @register_tool
    async def assign_roles(self, ctx: DuckContext):
        """Gets available roles, lets the user select the relevant ones, and assigns them"""
        server_id = ctx.guild_id
        thread_id = ctx.thread_id
        user_id = ctx.author_id
        timeout = ctx.timeout or 300
        settings = self._settings
        # Get roles and selection
        if settings.get('roles') is None:
            duck_logger.info("No roles configured for this server. Using authenticated user role only.")
            role_name = settings['authenticated_user_role_name']
            guild: Guild = await self._get_guild(server_id)
            member = await guild.fetch_member(user_id)

            # Find role by name instead of ID
            role = utils.get(guild.roles, name=role_name)  # This function is from the discord.utils module
            if not role:
                raise ValueError(f"Role '{role_name}' not found in guild '{guild.name}'.")


            selected_roles = [role]
            role_names = ", ".join(role.name for role in selected_roles)
            await member.add_roles(role, reason="User registration")
            await self._send_message(thread_id, f"Successfully gave you the following roles: {role_names}")
            return role_names

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

            # Get member's current roles
            current_role_ids = await self.get_user_roles(member)

            # Get the role objects
            selected_roles = []
            already_roles = []
            for role_id in selected_role_ids:
                if role_id in current_role_ids:
                    already_roles.append(role_id)
                    continue
                role = guild.get_role(role_id)
                if role:
                    selected_roles.append(role)

            if not selected_roles and already_roles:
                duck_logger.info('User already has selected roles, no need to add')
            elif not selected_roles:
                duck_logger.info('Could not lookup role objects from the selected role IDs.')

            # Assign roles
            new_roles = [role for role in selected_roles if role not in member.roles]
            if new_roles:
                await member.add_roles(*new_roles, reason="User registration")

            if already_roles:
                already_added_roles = [guild.get_role(role_id) for role_id in already_roles]
                already_added_role_names = ", ".join(role.name for role in already_added_roles)
                await self._send_message(
                    thread_id,
                    f"You already have these selected roles: {already_added_role_names}"
                )

        # Send confirmation message
        role_names = ", ".join(role.name for role in selected_roles)
        if not selected_roles:
            await self._send_message(thread_id, f"No new roles added")
        else:
            await self._send_message(thread_id, f"Successfully gave you the following roles: {role_names}")
        return role_names

    @step
    async def _is_suspicious(self, name: str) -> tuple[bool, str]:
        """Check if a nickname looks suspicious."""

        if len(name) < 3 or len(name) > 64:
            return True, "Name length not typical"
        if any(char.isdigit() for char in name):
            return True, "Contains digits"
        if any(char in "!@#$%^&*()_+=~`[]{};:'\",.<>?/\\|" for char in name):
            return True, "Contains unusual symbols"
        if any(ord(char) > 10000 for char in name):
            return True, "Contains emojis/unicode"

        return False, ""

    @step
    async def _assign_nickname(
            self,
            ctx: DuckContext,
            name: str
    ) -> tuple[bool, str]:
        """Try assigning the nickname, return (success, reason)."""
        try:
            guild: Guild = await self._get_guild(ctx.guild_id)
            member = await guild.fetch_member(ctx.author_id)

            suspicious, reason = await self._is_suspicious(name)
            if suspicious:
                return False, reason

            if member.guild.owner_id == member.id:
                return False, "Cannot change the server owner's nickname"

            await member.edit(nick=name, reason="Student registration")
            return True, "Nickname set successfully"

        except Exception as e:
            duck_logger.info(f"Error assigning nickname: {e}")
            return False, "Unexpected error"

    @step
    @register_tool
    async def nickname_flow(
            self,
            ctx: DuckContext,
    ):
        """Handle full nickname assignment flow with retries and TA escalation."""
        max_retries = self._settings['max_retries'] or 3
        thread_id = ctx.thread_id
        """Handle full nickname assignment flow with retries and TA escalation."""
        for attempt in range(max_retries + 1):
            name = await self._get_names(thread_id, ctx.timeout)

            success, reason = await self._assign_nickname(ctx, name)
            if success:
                await self._send_message(thread_id, f"Your nickname has been set to **{name}**")
                return name, None
            if attempt < max_retries:
                await self._send_message(thread_id, f"Please try again.")
            else:
                return name, reason
