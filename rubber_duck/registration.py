import asyncio

from quest import step


class RegistrationWorkflow:
    def __init__(self, send_message, fetch_message, create_thread, wait_for):
        self._send_message = step(send_message)
        self._fetch_message = fetch_message
        self._create_thread = step(create_thread)
        self._wait_for = wait_for

    async def __call__(self, *args):
        return await self.start(*args)

    async def start(self, user_id, channel_id):
        # Create a thread for the registration process
        thread_id = await self._create_thread(channel_id, f"Registration for <@{user_id}>")

        # Send the initial registration message in the thread
        await self._send_message(
            thread_id,
            f"Hello <@{user_id}>, welcome to the registration process! Please follow the prompts."
        )

        # Registration prompts

        await self._send_message(thread_id, "What is your BYU Net ID?")
        while True:
            byu_id_response = await self._fetch_user_response(user_id, thread_id)
            if not self._validate_byu_id(byu_id_response.content):
                await self._send_message(thread_id, "Invalid BYU Net ID. Please try again.")
            else:
                break

        await self._send_message(thread_id, "What is your preferred username?")
        username_response = await self._fetch_user_response(user_id, thread_id)

        # Confirm registration
        await self._send_message(
            thread_id,
            f"Thank you, {username_response.content}. Confirm registration by reacting with ✅."
        )

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

    def _validate_byu_id(self, byu_id):
        """Placeholder BYU Net ID validation logic."""
        # Replace with actual validation (e.g., regex or API check)
        return byu_id.isalnum() and len(byu_id) == 9