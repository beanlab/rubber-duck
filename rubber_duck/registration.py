from quest import step
import canvasapi

class RegistrationWorkflow:
    def __init__(self,
                 send_message,
                 fetch_message,
                 timeout = 300
                 ):
        self._send_message = step(send_message)
        self._fetch_message = step(fetch_message)


    async def start(self, user_id, channel_id):
        # Create a thread for the registration process
        thread = await message.channel.create_thread(
            name=f"Registration for {message.author.name}",
            auto_archive_duration=1440  # Use the duration as required
        )

        # Send the initial registration message in the thread
        await self._send_message(thread_id,
            f"Hello {message.author.mention}, welcome to the registration process! Please follow the prompts."
        )
        await self._send_message(channel_id, f"Hello <@{user_id}>, welcome! Let's get you registered.")
        await self._send_message(channel_id, "What is your BYU net ID?")
        byu_id = await self._fetch_user_response(user_id,channel_id)
        #TODO add canvas logic here to check if its valid or not.What
        await self._send_message(channel_id, "What is your preferred username?")
        username_response = await self._fetch_user_response(user_id, channel_id)

        # Confirm registration
        await self._send_message(channel_id, f"Thank you, {username_response.content}. Confirm registration by reacting with ✅.")

    async def _fetch_user_response(self, user_id, channel_id):
        def check(m):
            return m.author.id == user_id and m.channel.id == channel_id

        return await self._fetch_message(channel_id, check)
