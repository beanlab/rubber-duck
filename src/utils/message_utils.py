from quest import queue
from ..utils.protocols import Message
import asyncio


async def wait_for_message(timeout=300) -> Message | None:
    async with queue('messages', None) as messages:
        try:
            message: Message = await asyncio.wait_for(messages.get(), timeout)
            return message
        except asyncio.TimeoutError:  # Close the thread if the conversation has closed
            return None

