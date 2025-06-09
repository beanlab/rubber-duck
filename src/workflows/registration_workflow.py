import re
import uuid

from discord import Guild
from quest import step

from ..utils.config_types import RegistrationSettings
from ..utils.send_email import EmailSender
from ..utils.logger import duck_logger
from ..utils.protocols import Message
from ..views.registration_views import GetNetIDView, RoleSelectionView, EmailConfirmationView

WELCOME_MESSAGE = "Hello, welcome to the registration process! Please click the button below to begin."
CONFIRM_MESSAGE = "We sent a code to your BYU email.\nEnter the code below and click Submit, or click Resend to get a new code."
FAILED_EMAIL_MESSAGE = 'Unable to validate your email. Please talk to a TA or your instructor.'


class RegistrationWorkflow:
    def __init__(self,
                 name: str,
                 send_message,
                 get_channel,
                 fetch_guild,
                 email_sender: EmailSender,
                 settings: RegistrationSettings
                 ):
        self.name = name

        self._send_message = step(send_message)
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self._email_sender = email_sender
        self._settings = settings

    async def __call__(self, thread_id: int, initial_message: Message):
        # Start the registration process
        net_id = await self._get_net_id(thread_id)

        # Get and verify the email
        if not await self._confirm_registration_via_email(net_id, thread_id):
            await self._send_message(thread_id, FAILED_EMAIL_MESSAGE)
            return

        # Assign Discord roles
        server_id = initial_message['guild_id']
        await self._assign_roles(server_id, thread_id, initial_message['author_id'], self._settings)

    def _generate_token(self):
        code = str(uuid.uuid4().int)[:6]
        return code

    @step
    async def _get_net_id(self, thread_id):
        try:
            # Create and send the registration view
            netid_view = GetNetIDView()
            await self._send_message(thread_id, "Please enter your BYU Net ID to begin the registration process.")
            await self._send_message(thread_id,view=netid_view)

            # Wait for the view to be completed
            await netid_view.wait()

            if not netid_view.net_id:
                await self._send_message(thread_id, "Registration failed: No Net ID provided. Please start over.")
                raise ValueError("No Net ID provided")

            return netid_view.net_id

        except Exception as e:
            duck_logger.error(f"Setup failed: {e}")
            await self._send_message(thread_id, "Registration setup failed. Please contact an administrator.")
            raise

    @step
    async def _confirm_registration_via_email(self, net_id, thread_id):
        email = f'{net_id}@byu.edu'  # You might want to collect the email address first
        token = self._generate_token()
        if not self._email_sender.send_email(email, token):
            return False

        max_attempts = 3
        attempts = 0

        while attempts < max_attempts:
            view = EmailConfirmationView()
            await self._send_message(thread_id, CONFIRM_MESSAGE, view=view)

            # Wait for the view to be completed
            await view.wait()

            if hasattr(view, 'resend') and view.resend:
                token = self._email_sender.send_email(email, token)
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
                    await self._send_message(thread_id,
                                             "Too many invalid attempts. Please exit the thread and start again.")
                    return False

        return False

    @step
    async def _select_roles(self, thread_id, available_roles):
        # Create and show role selection view
        view = RoleSelectionView(available_roles)
        await self._send_message(
            thread_id,
            "Please select your lecture section (and if applicable, select your lab section).\n"
            "You can find your lab and lecture sections in BYU MyMap.\n",
            view=view
        )

        # Wait for role selection
        await view.wait()

        if not view.selected_roles:
            await self._send_message(thread_id, "No roles selected. Please try again.")
            return []

        return view.selected_roles

    @step
    async def _get_available_roles(
            self, thread_id: int, server_id: int, settings: RegistrationSettings
    ) -> tuple[list[int], int]:
        """Gets available guild roles and the authenticated user role"""
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
            authenticated_user_role_id = None
            for role in guild.roles:
                if role.name == settings['authenticated_user_role_name']:
                    authenticated_user_role_id = role.id
                    continue

                for pattern_info in role_patterns:
                    if re.search(pattern_info["pattern"], role.name):
                        available_roles.append({
                            "id": role.id,
                            "name": role.name,
                            "description": pattern_info["description"]
                        })
                        break

            if authenticated_user_role_id is None:
                raise ValueError('No authenticated_user_role_name configured for this server '
                                 '(or it didn\'t match any existing role names).')

            return available_roles, authenticated_user_role_id

        except Exception as e:
            duck_logger.error(f"Error getting guild roles: {str(e)}")
            await self._send_message(thread_id, "Error getting available roles. Please contact an administrator.")
            raise

    @step
    async def _assign_roles(self, server_id: int, thread_id: int, user_id: int, settings: dict):
        """Gets available roles, lets the user select the relevant ones, and assigns them"""
        try:
            # Get roles and selection
            available_roles, authenticated_role_id = await self._get_available_roles(thread_id, server_id, settings)
            if available_roles:
                selected_role_ids = await self._select_roles(thread_id, available_roles)
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
