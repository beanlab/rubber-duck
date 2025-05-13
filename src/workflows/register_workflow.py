import asyncio

from quest import step, queue, alias
from discord import Member

from ..utils.canvas_api import CanvasApi
from ..utils.email_confirmation import EmailConfirmation
from ..utils.protocols import Message

intro_message = (
    "Hello! My name is Duck, and I'm your friendly registration assistant.\n "
    "I'm here to help you with your registration process.\n "
    "Let's get started!\n "
    "What is your BYU Net ID?\n\n"
)

invalid_id_message = (
    "It seems like the Net ID you provided is invalid.\n"
    "Please try again and enter a valid BYU Net ID.\n"
)


class RegistrationWorkflow:
    def __init__(self,
                 send_message,
                 create_thread,
                 canvas_api: CanvasApi,
                 email_confirmation: EmailConfirmation,
                 get_channel,
                 fetch_guild
                 ):
        self._send_message = step(send_message)
        self._create_thread = step(create_thread)
        self._canvas_api = canvas_api
        self._email_confirmation = email_confirmation
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self.current_user: Member = None

    async def __call__(self, thread_id: int, prompt: str, initial_message: Message):
        await self._canvas_api
        await self._send_message(thread_id, intro_message)
        # Get the Net ID

        net_id = self._get_net_id(thread_id, initial_message)
        self._verify_net_id(net_id)

        # Get the course ID
        # Get the canvas object and confirm enrollment
        # Get the send_email
        #

    async def _get_net_id(self, thread_id: int, initial_message: Message)->str:
        """
        Get the Net ID from the user.
        """
        async with alias(str(thread_id)), queue("messages", None) as messages:
            while True:
                try:
                    # Waiting for a response from the user
                    message: Message = await asyncio.wait_for(messages.get(), timeout=120)
                    net_id = message['content'].strip()

                except asyncio.TimeoutError:  # Close the thread if the conversation has closed
                    break

                return net_id

    #TODO figure out if we need the step decorator here.
    async def _is_valid_net_id(self, guild_id, net_id):
        users = self._canvas_api.get_canvas_users(guild_id)
        return net_id in users


