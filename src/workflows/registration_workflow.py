import asyncio

from discord import Guild, Member
from quest import step, queue, alias

from ..utils.canvas_api import CanvasApi
from ..utils.email_confirmation import EmailConfirmation
from ..utils.logger import duck_logger
from ..utils.protocols import Message

welcome_message = f"Hello, welcome to the registration process! Please follow the prompts."
confirm_message ="Check your BYU Email to confirm your registration.\n Type in your code into the chat to confirm your registration."
failed_email_message= 'Unable to validate your email. Please talk to a TA or your instructor.'
class RegistrationWorkflow:
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
        author_name, server_id, user_id = self._parse_settings(initial_message)
        self._canvas_api = CanvasApi(server_id, settings)
        self._email_confirmation = EmailConfirmation(settings['sender_email'])
        self._canvas_api()

        await self._send_message(thread_id, welcome_message,)

        # Get the ID
        net_id = await self._get_net_id(server_id, thread_id, author_name)

        # Verify it via outlook.
        if not await self._confirm_registration_via_email(thread_id, net_id):
            await self._send_message(failed_email_message)
            return

        # add the role

    def _parse_settings(self, initial_message):
        author_name = initial_message['author_name']
        guild_id = initial_message['guild_id']
        user_id = initial_message['author_id']
        return author_name, guild_id, user_id

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