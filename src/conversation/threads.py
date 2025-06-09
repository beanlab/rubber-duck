from ..utils.config_types import DuckContext
from ..utils.protocols import Message, CreateThread, SendMessage


class SetupPrivateThread:
    def __init__(self, create_thread: CreateThread, send_message: SendMessage):
        self._create_thread = create_thread
        self._send_message = send_message

    async def __call__(self, parent_channel_id: int, author_mention: str, title: str) -> int:
        thread_id = await self._create_thread(
            parent_channel_id,
            title[:20]
        )

        # Send welcome message to add the user to the thread
        await self._send_message(thread_id, f'{author_mention}')

        # Notify the user in the original channel of the new thread
        await self._send_message(
            parent_channel_id,
            f"{author_mention} Click here to join the conversation: <#{thread_id}>"
        )

        return thread_id
