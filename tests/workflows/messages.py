from collections.abc import Callable
from contextlib import AbstractAsyncContextManager


class MemoryMessages:
    # Connect an in-memory implementation of the existing messaging interface to recording.
    def __init__(self, record: Callable[[dict], None]):
        ...

    # Create an isolated conversation thread identifier and record its parent channel.
    async def create_thread(self, parent_channel_id: int, title: str) -> int:
        ...

    # Record delivered text and return its message identifier.
    async def send_text(self, channel_id: int, text: str) -> int:
        ...

    # Preserve a delivered image's bytes, filename, and destination.
    async def send_image(self, channel_id: int, filename: str, image_data: bytes) -> None:
        ...

    # Preserve a delivered attachment's bytes, filename, and destination.
    async def send_attachment(self, channel_id: int, filename: str, file_data: bytes) -> None:
        ...

    # Preserve a delivered table's headers, rows, and destination.
    async def send_table(
        self, channel_id: int, header: list[str], rows: list[list[str]]
    ) -> None:
        ...

    # Record reactions without sending them through Discord.
    async def add_reaction(self, channel_id: int, message_id: int, emoji: str) -> None:
        ...

    # Provide the typing context manager expected by the production workflows.
    def typing(self, channel_id: int) -> AbstractAsyncContextManager[None]:
        ...
