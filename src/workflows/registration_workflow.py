import asyncio

from discord import Guild
from quest import step, queue, alias

from ..utils.canvas_api import CanvasApi
from ..utils.email_confirmation import EmailConfirmation
from ..utils.logger import duck_logger
from ..utils.protocols import Message

welcome_message = "Hello, welcome to the registration process! Please follow the prompts."
confirm_message = "We sent a code to your byu email.\n Type in your code into the chat to confirm your identity."
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

        # Get and verify the Net ID
        net_id = await self._get_net_id(server_id, thread_id, author_name)
        if not await self._confirm_registration_via_email(thread_id, net_id):
            await self._send_message(thread_id, failed_email_message)
            return

        # Assign Discord roles
        await self._assign_role(server_id, thread_id, net_id, initial_message['author_id'])

    @step
    async def _set_up(self, initial_message, settings, thread_id):
        try:
            author_name = initial_message['author_name']
            server_id = initial_message['guild_id']
            
            # Initialize Canvas API
            try:
                self._canvas_api = CanvasApi(server_id, settings)
            except Exception as e:
                duck_logger.error(f"Failed to initialize Canvas API: {e}")
                await self._send_message(thread_id, "Error connecting to Canvas. Please contact an administrator.")
                raise
                
            self._email_confirmation = EmailConfirmation(settings['sender_email'])
            await self._send_message(thread_id, welcome_message)
            return author_name, server_id
            
        except Exception as e:
            duck_logger.error(f"Setup failed: {e}")
            await self._send_message(thread_id, "Registration setup failed. Please contact an administrator.")
            raise

    @step
    async def _get_net_id(self, guild_id, thread_id, author_name) -> str:
        await self._send_message(thread_id, "What is your BYU Net ID?")
        
        async with alias(str(thread_id) + author_name), queue("messages", None) as message_queue:
            while True:
                message: Message = await asyncio.wait_for(message_queue.get(), timeout=120)
                net_id = message['content'].strip()
                
                if self._canvas_api.get_user_enrollment(net_id):
                    return net_id
                    
                await self._send_message(thread_id, "Invalid BYU Net ID. Please try again.")

    @step
    async def _confirm_registration_via_email(self, thread_id, net_id):
        email = f'{net_id}@byu.edu'
        token = self._email_confirmation.prepare_email(email)
        if not token:
            return False
            
        await self._send_message(thread_id, confirm_message)

        async with queue('messages', None) as messages:
            try:
                message: Message = await asyncio.wait_for(messages.get(), timeout=300)
                if message['content'].strip() == token:
                    await self._send_message(thread_id, "Successfully registered. Adding you to your class!")
                    return True
                    
                duck_logger.error(f"Token mismatch: {message['content'].strip()} != {token}")
                await self._send_message(thread_id, "Invalid token. Please try again.")
                return False
                
            except asyncio.TimeoutError:
                await self._send_message(thread_id, "Timed out waiting for token. Please exit the discord thread and start a new conversation")
                return False

    @step
    async def _assign_role(self, server_id: str, thread_id: int, net_id: str, user_id: int):
        """Assigns the appropriate Discord roles based on Canvas enrollment"""
        try:
            # Get user's enrollment info
            enrollment = self._canvas_api.get_user_enrollment(net_id)
            if not enrollment:
                await self._send_message(thread_id, "Error: Could not find your enrollment information.")
                return

            enrollment_type, section_name = enrollment
            role_name = self.ROLE_MAPPING.get(enrollment_type, 'Student')

            # Get Discord guild and roles
            guild: Guild = await self._get_guild(server_id)
            if not guild:
                duck_logger.error(f"Could not find Discord server with ID {server_id}")
                await self._send_message(thread_id, "Error: Could not find Discord server.")
                return

            # Get the member
            member = await guild.fetch_member(user_id)
            if not member:
                duck_logger.error(f"Could not find member with ID {user_id} in server {server_id}")
                await self._send_message(thread_id, "Error: Could not find your Discord account in the server.")
                return

            # Find and assign roles
            roles = await guild.fetch_roles()
            enrollment_role = next((r for r in roles if r.name == role_name), None)
            section_role = next((r for r in roles if r.name == section_name), None)

            if not enrollment_role or not section_role:
                missing = []
                if not enrollment_role: missing.append(role_name)
                if not section_role: missing.append(section_name)
                duck_logger.error(f"Missing roles in server {server_id}: {', '.join(missing)}")
                await self._send_message(thread_id, f"Error: Could not find required roles. Please contact an administrator.")
                return

            # Assign roles
            await member.add_roles(enrollment_role, section_role, reason="Canvas course registration")
            await self._send_message(
                thread_id,
                f"Successfully assigned you the {role_name} role and {section_name} section role!"
            )

        except Exception as e:
            duck_logger.error(f"Error assigning roles: {str(e)}")
            await self._send_message(thread_id, "Error assigning roles. Please contact an administrator.")
