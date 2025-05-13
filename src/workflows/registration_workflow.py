import asyncio
import os

import requests
from canvasapi.enrollment import Enrollment
from canvasapi.user import User
from quest import step, queue, alias
from discord import Member

from ..utils.OAuthServer import OAuthServer
from ..utils.canvas_api import get_course
from ..utils.protocols import Message

client_id = os.getenv("CLIENT_ID")
redirect_uri = os.getenv("REDIRECT_URI")

intro_message = (
    "Hello! My name is Duck, and I'm your friendly registration assistant.\n"
    "I'm here to help you get set up for your classes.\n\n"
    "✅ Let's start by verifying your credentials.\n"
    "Click the link below to log in with your BYU Canvas account:\n"
    f"https://byu.instructure.com/login/oauth2/auth?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}"
)
timeout_message ="❌ Login timed out. Please try again."
success_message = f"✅ Registration complete!"

class RegistrationWorkflow:
    def __init__(self,
                 send_message,
                 get_channel,
                 fetch_guild,
                 ):
        self._send_message = step(send_message)
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self._api_url = "https://byu.instructure.com"
        self._canvas_token = None
        self.current_user: Member = None
        self.oauth_server = None

    async def __call__(self, thread_id: int, prompt: str, initial_message: Message):
        # Start Flask Server for the OAuth2 callback
        self.oauth_server = OAuthServer(self)
        self.oauth_server.run()

        # Verify user
        await self._send_message(thread_id, intro_message)

        for _ in range(30):
            if self._canvas_token:
                break
            await asyncio.sleep(1)

        if not self._canvas_token:
            await self._send_message(thread_id, timeout_message)
            return

        # Proceed with the registration workflow using the token
        course = get_course(
            self._canvas_token,
            self._api_url,
            self._get_course_id(),  # Replace with actual course ID
        )
        role = course["user_id"]["enrollment_type"]

        await self._assign_role(role)

        # Check if the user is already enrolled
        user_data = await self._get_user_data(self._canvas_token)

        # Clean things up
        await self._send_message(thread_id, success_message)
        self.oauth_server.stop()

    def receive_token(self, state, token):
        """This method will be called by the Flask server to pass the token."""
        self._canvas_token = token

    def _get_course_id(self) -> int:
        # TODO: Figure out where we get the course ID from
        """
        This method should retrieve the course ID from the guild configuration.
        For now, we'll just return a placeholder value.
        """
        pass

    async def _get_user_data(self, token) -> User:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        api_url = f"{self._api_url}/api/v1/users/self"

        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            user_data = response.json()
            return user_data
        else:
            raise Exception(f"Failed to fetch user data: {response.status_code} - {response.text}")


    async def _get_enrollment(self, course_id) -> Enrollment:
        pass

    async def _assign_role(self, role):