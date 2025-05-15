import asyncio

from discord import Guild
from quest import step, queue, alias

from ..utils.canvas_api import CanvasApi
from ..utils.email_confirmation import EmailConfirmation
from ..utils.logger import duck_logger
from ..utils.protocols import Message

welcome_message = "Hello, welcome to the registration process! Please follow the prompts."
confirm_message = "We sent a code o your byu email.\n Type in your code into the chat to confirm your identity."
failed_email_message = 'Unable to validate your email. Please talk to a TA or your instructor.'

class RegistrationWorkflow:
    # Map Canvas enrollment types to Discord role names
    ROLE_MAPPING = {
        'TeacherEnrollment': 'Faculty',
        'StudentEnrollment': 'Student',
        'TaEnrollment': 'TA',
        'DesignerEnrollment': 'TA',
        'ObserverEnrollment': 'TA'
    }

    def __init__(self,
                 send_message,
                 get_channel,
                 fetch_guild
                 ):
        self._send_message = step(send_message)
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self._canvas_api = None
        self._email_confirmation = None

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):
        # Start the registration process
        author_name, server_id = await self._set_up(initial_message, settings, thread_id)

        # Get the ID
        net_id = await self._get_net_id(server_id, thread_id, author_name)

        # Verify it via outlook.
        if not await self._confirm_registration_via_email(thread_id, net_id):
            await self._send_message(failed_email_message)
            return

        # Get user's Canvas enrollment type and assign Discord role
        await self._assign_role(server_id, thread_id, net_id, initial_message['author_id'])

    @step
    async def _set_up(self, initial_message, settings, thread_id):
        # Extract info from initial message
        author_name = initial_message['author_name']
        server_id = initial_message['guild_id']

        # Set up dependencies
        self._canvas_api = CanvasApi(server_id, settings)
        self._email_confirmation = EmailConfirmation(settings['sender_email'])

        # Send welcome message
        await self._send_message(thread_id, welcome_message)

        return author_name, server_id

    @step
    async def _get_net_id(self, guild_id, thread_id, author_name) -> str:
        await self._send_message(thread_id, "What is your BYU Net ID?")
        timeout = 120

        async with alias(str(thread_id)+author_name), queue("messages", None) as message_queue:
            while True:
                message: Message = await asyncio.wait_for(message_queue.get(), timeout)
                net_id = message['content'].strip()

                if not await self._is_valid_net_id(guild_id, net_id):
                    await self._send_message(thread_id, "Invalid BYU Net ID. Please try again.")
                    continue

                return net_id

    @step
    async def _is_valid_net_id(self, guild_id, net_id):
        users = self._canvas_api.get_canvas_users(guild_id)
        return net_id in users

    @step
    async def _confirm_registration_via_email(self, thread_id, net_id):
        email = f'{net_id}@byu.edu'
        token = self._email_confirmation.prepare_email(email)
        if not token:
            pass
        await self._send_message(thread_id, confirm_message)

        async with queue('messages', None) as messages:
            while True:
                try:
                    message: Message = await asyncio.wait_for(messages.get(), timeout=300)
                    res_token = message['content'].strip()
                    if res_token == token:
                        await self._send_message(thread_id, "Successfully registered. Adding you to your class! ")
                        return True
                    else:
                        duck_logger.error(f"Token mismatch: {res_token} != {token}")
                        await self._send_message(thread_id, "Invalid token. Please try again.")
                except asyncio.TimeoutError:
                    await self._send_message(thread_id, "Timed out waiting for token. Please exit the discord thread and start a new conversation")
                    return False

    @step
    async def _assign_role(self, server_id: str, thread_id: int, net_id: str, user_id: int):
        """
        Assigns the appropriate Discord roles based on:
        1. The user's Canvas enrollment type (Student/Faculty/TA)
        2. The user's section number
        """
        try:
            # Get the user's enrollment type and section from Canvas
            section_data = self._canvas_api.section_enrollments[server_id]
            
            # Find the user's section and enrollment type
            user_section = None
            enrollment_type = None
            for section_number, data in section_data.items():
                if net_id in data['enrollments']:
                    user_section = section_number
                    enrollment_type = data['enrollments'][net_id]['enrollment_type']
                    break

            if not user_section or not enrollment_type:
                await self._send_message(thread_id, "Error: Could not find your enrollment information.")
                return

            # Map the enrollment type to a role name
            role_name = self.ROLE_MAPPING.get(enrollment_type, 'Student')  # Default to Student if unknown type

            # Get Discord guild and roles
            guild: Guild = await self._get_guild(server_id)
            if not guild:
                duck_logger.error(f"Could not find Discord server with ID {server_id}")
                await self._send_message(thread_id, "Error: Could not find Discord server.")
                return

            # Find both the enrollment role and section role
            roles = await guild.fetch_roles()
            enrollment_role = next((r for r in roles if r.name == role_name), None)
            section_role = next((r for r in roles if r.name == user_section), None)
            
            if not enrollment_role:
                duck_logger.error(f"Could not find role '{role_name}' in server {server_id}")
                await self._send_message(thread_id, f"Error: Could not find role '{role_name}' in server.")
                return

            if not section_role:
                duck_logger.error(f"Could not find section role '{user_section}' in server {server_id}")
                await self._send_message(thread_id, f"Error: Could not find section role '{user_section}' in server.")
                return

            # Get the member and assign both roles
            member = await guild.fetch_member(user_id)
            if not member:
                duck_logger.error(f"Could not find member with ID {user_id} in server {server_id}")
                await self._send_message(thread_id, "Error: Could not find your Discord account in the server.")
                return

            await member.add_roles(enrollment_role, reason="Canvas course registration - enrollment type")
            await member.add_roles(section_role, reason="Canvas course registration - section assignment")
            
            await self._send_message(
                thread_id, 
                f"Successfully assigned you the {role_name} role and {user_section} section role based on your Canvas enrollment!"
            )

        except Exception as e:
            duck_logger.error(f"Error assigning roles: {str(e)}")
            await self._send_message(thread_id, "Error assigning roles. Please contact an administrator.")