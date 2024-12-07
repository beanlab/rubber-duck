import asyncio

import os
from dotenv import load_dotenv
from quest import step
from canvas_api import CanvasApi
from email_confirmation import EmailConfirmation

# load_dotenv()
# token = os.getenv("CANVAS_TOKEN")
COURSE_ID = os.getenv("COURSE_ID")
# BASE_URL = "https://byu.instructure.com/api/v1"


class RegistrationWorkflow:
    def __init__(self, send_message, fetch_message, create_thread, wait_for, assign_role, canvas_api: CanvasApi, email_confirmation: EmailConfirmation, get_guild, canvas_config):
        self._send_message = step(send_message)
        self._fetch_message = fetch_message
        self._create_thread = step(create_thread)
        self._wait_for = wait_for
        self._assign_user_role = assign_role
        self._canvas_users = {}
        self._canvas_api = canvas_api
        self._email_confirmation = email_confirmation
        self._get_guild = get_guild
        self._canvas_config = canvas_config

    async def __call__(self, user_id, channel_id, guild_id, member_id):
        return await self.start(user_id, channel_id, guild_id,member_id)

    async def start(self, user_id, channel_id, guild_id, member_id):
        # Create a thread for the registration process
        guild = self._get_guild(guild_id)
        member = await guild.fetch_member(member_id)
        thread_id = await self._create_thread(channel_id, f"Registration for {member.name}")

        await self._send_message(
            thread_id,
            f"Hello <@{user_id}>, welcome to the registration process! Please follow the prompts."
        )

        await self._send_message(thread_id, "What is your BYU Net ID?")
        while True:
            byu_id_response = await self._fetch_user_response(user_id, thread_id)
            self._collect_canvas_data()
            if not self._validate_byu_id(byu_id_response.content, thread_id):
                await self._send_message(thread_id, "Invalid BYU Net ID. Please try again.")
            else:
                break

        name, email, canvas_role= await self._confirmation_check(byu_id_response.content, thread_id)

        await self._confirm_registration_via_email(thread_id, user_id, email)
        await self._assign_user_role(member_id, canvas_role, guild_id,thread_id)

    async def _confirm_registration_via_email(self, thread_id, user_id, email):
        await self._send_message(thread_id, "Check your BYU Email to confirm your registration. Type in your code into the chat to confirm your registration.")
        while True:
            users_token_response = await self._fetch_user_response(user_id, thread_id)
            if self._email_confirmation.confirm_token(email,users_token_response.content):
                await self._send_message(thread_id, "Your registration was successful.")
                break
            else:
                await self._send_message(thread_id, "The code you entered is incorrect. Please try again.")
        self._email_confirmation.send_email_with_token(email, sender="<byu-cs-course-ops@cs.byu.edu>")


    def _collect_canvas_data(self):
        self._canvas_config = []
        self._canvas_api.get_canvas_users(COURSE_ID)
        # if not self._canvas_api.was_called_within_last_hour():
        #     self._canvas_api.connect_canvas_api()
        #     self._canvas_users = self._canvas_api.get_canvas_users()
        # else:
        #     self._send_message(self._send_message, "Please wait an hour before continuing")

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

    async def _confirmation_check(self, byu_id, thread_id):
        name,email,canvas_role = self._canvas_users[byu_id]
        await self._send_message(thread_id, f"Is this correct?\n{name}\n{byu_id}\n{email}")

        return name,email,canvas_role

    async def _validate_byu_id(self, byu_id,thread_id):
        if len(self._canvas_users) == 0:
            if self._canvas_users == 0:
                await self._send_message(thread_id, "Canvas is processing too many requests. Please try again later.")


        if byu_id in self._canvas_users:
            return True
        else:
            return False