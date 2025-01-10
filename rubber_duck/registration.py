import asyncio

from rubber_duck import Message
from quest import step, queue
from canvas_api import CanvasApi
from email_confirmation import EmailConfirmation


class RegistrationWorkflow:
    def __init__(self, send_message, fetch_message, create_thread, wait_for, assign_role, canvas_api: CanvasApi,
                 email_confirmation: EmailConfirmation, get_guild):
        self._send_message = step(send_message)
        self._fetch_message = fetch_message
        self._create_thread = step(create_thread)
        self._get_guild = get_guild
        self._assign_user_role = assign_role

        self._canvas_api = canvas_api
        self._email_confirmation = email_confirmation

    async def __call__(self, user_id, channel_id, guild_id):
        return await self.start(user_id, channel_id, guild_id)

    async def start(self, user_id, channel_id, guild_id):
        # Create a thread for the registration process
        thread_id = self._setup_thread(guild_id, channel_id, user_id)

        await self._send_message(
            thread_id,
            f"Hello <@{user_id}>, welcome to the registration process! Please follow the prompts."
        )

        net_id = await self._get_net_id(guild_id, thread_id, user_id)

        if not await self._confirm_registration_via_email(guild_id, thread_id, user_id, net_id):
            await self._send_message('Unable to validate your email. Please talk to a TA or your instructor.')
            return

        await self._assign_user_role(user_id, canvas_role, guild_id, thread_id)

    @step
    async def _setup_thread(self, guild_id, parent_channel_id, user_id) -> int:
        guild = self._get_guild(guild_id)
        member = await guild.fetch_member(user_id)
        return await self._create_thread(parent_channel_id, f"Registration for {member.name}")

    @step
    async def _get_net_id(self, guild_id, thread_id, user_id) -> str:
        await self._send_message(thread_id, "What is your BYU Net ID?")

        timeout = 60
        async with queue('messages', None) as messages:
            while True:
                message: Message = await asyncio.wait_for(messages.get(), timeout)
                net_id = message['content'].strip()
                if not await self._is_valid_net_id(guild_id, net_id):
                    await self._send_message(thread_id, "Invalid BYU Net ID. Please try again.")
                return net_id

    @step
    async def _is_valid_net_id(self, guild_id, net_id):
        users = self._canvas_api.get_canvas_users(guild_id)
        return net_id in users

    async def _confirm_registration_via_email(self, guild_id, thread_id, user_id, net_id):

        token = self._generate_token()

        email = f'{net_id}@byu.edu'
        subject = "Registration confirmation"  # TODO - discord server name?
        body = f"""
        <html>
        <body>
            <p>Hello,</p>
            <p>Here is your secret code:</p>
            <p style="text-align: center; font-size: 24px; font-weight: bold;">{token}</p>
            <p>Use this token on Discord to verify your email.</p>
        </body>
        </html>
        """
        # Email sender class rename, include only one function.
        if not await self._email_confirmation.send_email(email, subject, body):
            pass   # TODO - email failed to send

        await self._send_message(thread_id, "Check your BYU Email to confirm your registration. "
                                            "Type in your code into the chat to confirm your registration.")

        async with queue('messages', None) as messages:
            while True:
                users_token_response = await messages.get()
                if users_token_response != token:
                    pass ## TODO - wrong token
                return True

                # if self._email_confirmation.confirm_token(email, users_token_response.content):
                #     await self._send_message(thread_id, "Your registration was successful.")
                #     break
                # else:
                #     await self._send_message(thread_id, "The code you entered is incorrect. Please try again.")

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
