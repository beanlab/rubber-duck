from typing import Protocol, TypedDict

from ..utils.config_types import FileData


class Attachment(TypedDict):
    attachment_id: int
    description: str
    filename: str
    size: int
    content: str


class Message(TypedDict):
    guild_id: int
    channel_name: str
    channel_id: int
    author_id: int
    author_name: str
    author_mention: str
    message_id: int
    content: str
    file: list[Attachment]


class SendMessage(Protocol):
    async def __call__(self, channel_id: int, message: str = None, file: FileData = None, view=None) -> int: ...


class EditMessage(Protocol):
    async def __call__(self, channel_id: int, message_id: int, new_content: str): ...


class AddReaction(Protocol):
    async def __call__(self, channel_id: int, message_id: int, reaction: str): ...


class ReportError(Protocol):
    async def __call__(self, msg: str, notify_admin: bool = False): ...


class Context(Protocol):
    async def __aenter__(self): ...

    async def __aexit__(self, exc_type, exc_val, exc_tb): ...


class IndicateTyping(Protocol):
    def __call__(self, channel_id: int) -> Context: ...


class CreateThread(Protocol):
    async def __call__(self, parent_channel_id: int, title: str) -> int: ...
