import asyncio

from discord import Guild, Member
from quest import step, queue, alias

from ..utils.canvas_api import CanvasApi
from ..utils.email_confirmation import EmailConfirmation
from ..utils.protocols import Message


confirm_message ="Check your BYU Email to confirm your registration.\n  Type in your code into the chat to confirm your registration."
class RegistrationWorkflow:
    def __init__(self,
                 send_message,
                 canvas_api: CanvasApi,
                 email_confirmation: EmailConfirmation,
                 get_channel,
                 fetch_guild
                 ):
        self._send_message = step(send_message)
        self._canvas_api = canvas_api
        self._email_confirmation = email_confirmation
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self.current_user:Member = None

    async def __call__(self, thread_id: int, settings: dict, initial_message: Message):
        # Start the registration process
        author_name, guild_id, user_id = self._parse_settings(initial_message)
        self._canvas_api(guild_id, settings)

        await self._send_message(
            thread_id,
            f"Hello, welcome to the registration process! Please follow the prompts."
        )

        # Get the ID
        net_id = await self._get_net_id(guild_id, thread_id, author_name)

        # Verify it via outlook.
        if not await self._confirm_registration_via_email(thread_id, net_id):
            await self._send_message('Unable to validate your email. Please talk to a TA or your instructor.')
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

    async def _confirm_registration_via_email(self, thread_id, net_id):
        email = f'{net_id}@byu.edu'
        token = await self._email_confirmation.send_email(email)
        if not token:
            pass

        await self._send_message(thread_id, confirm_message)

        async with queue('messages', None) as messages:
            while True:
                users_token_response = await messages.get()
                if users_token_response != token:
                    pass ## TODO - wrong token
                return True

    def _collect_canvas_data(self):
        self._canvas_config = []
        self._canvas_users = self._canvas_api.get_canvas_users(self._guild_id)

    async def _fetch_user_response(self, user_id, channel_id):
        """Fetch the next message from a user in the thread."""

        def check(message):
            return message.author.id == user_id and message.channel.id == channel_id

        # Await a message from the user that passes the check
        try:
            message = await self._wait_for('message', check=check, timeout=300.0)  # 5-minute timeout
            return message
        except asyncio.TimeoutError:
            # Send a message to the same channel where registration is happening
            await self._send_message(channel_id, "You took too long to respond. Please try again later.")
            return None

    async def _confirmation_check(self, byu_id, thread_id, user_id, channel_id):
        name, email, canvas_role = self._canvas_users[byu_id]
        await self._send_message(thread_id, f"Is this correct?\n{name}\n{email}")
        answer = await self._fetch_user_response(user_id, channel_id)
        if answer == "Yes":
            await self._send_message(channel_id, "Thank you for confirming.")
        else:
            await self._send_message(channel_id, "Thank you for your time, "
                                                 "please return back to the registration channel.")
            quit()

        return name, email, canvas_role

    async def _validate_byu_id(self, byu_id, thread_id):
        if len(self._canvas_users) == 0:
            if self._canvas_users == 0:
                await self._send_message(thread_id, "Canvas is processing too many requests. "
                                                    "Please try again later.")
        if byu_id in self._canvas_users:
            return True
        else:
            return False