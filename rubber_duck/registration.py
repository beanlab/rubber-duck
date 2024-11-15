from quest import step


class RegistrationWorkflow:
    def __init__(self,
                 send_message,
                 fetch_message,
                 timeout = 300
                 ):
        self._send_message = step(send_message)
        self._fetch_message = step(fetch_message)

    async def start(self, user_id, channel_id):
        await self._send_message(channel_id, f"Hello <@{user_id}>, welcome! Let's get you registered.")
        await self._send_message(channel_id, "What is your BYU net ID?")
        byu_id = await self._fetch_user_response(user_id,channel_id)
        #TODO add canvas logic here to check if its valid or not.
        await self._send_message(channel_id, "What is your preferred username?")
        username_response = await self._fetch_user_response(user_id, channel_id)

        # Confirm registration
        await self._send_message(channel_id, f"Thank you, {username_response.content}. Confirm registration by reacting with ✅.")

    async def _fetch_user_response(self, user_id, channel_id):
        def check(m):
            return m.author.id == user_id and m.channel.id == channel_id

        return await self._fetch_message(channel_id, check)
