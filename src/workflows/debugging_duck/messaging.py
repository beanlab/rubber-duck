from collections.abc import Awaitable, Callable

from ..utils.config_types import DuckContext
from ..utils.message_utils import wait_for_message
from ..utils.protocols import ConversationComplete, Message, SendMessage


WaitForMessage = Callable[[int], Awaitable[Message | None]]


class MessageRouting:
    def __init__(
        self,
        context: DuckContext,
        send_message: SendMessage,
        wait_message: WaitForMessage = wait_for_message,
    ):
        self.context = context
        self.send_message = send_message
        self.wait_for_message = wait_message

    async def send(self, content: str) -> str:
        message = str(content).strip()
        if message:
            await self.send_message(self.context.thread_id, message)
        return message

    async def wait(self) -> str:
        message = await self.wait_for_message(self.context.timeout)
        if message is None:
            raise ConversationComplete("This conversation has timed out.")

        return str(message["content"]).strip()
