import dataclasses
from typing import Protocol, TypedDict, Any

from ..utils.config_types import FileData, PlatformId


class Attachment(TypedDict):
    attachment_id: PlatformId
    description: str
    filename: str
    size: int
    url: str


class Message(TypedDict):
    guild_id: PlatformId
    channel_name: str
    channel_id: PlatformId
    author_id: PlatformId
    author_name: str
    author_mention: str
    message_id: PlatformId
    content: str
    files: list[Attachment]


class SendMessage(Protocol):
    async def __call__(self, channel_id: PlatformId, message: str = None, file: FileData = None) -> PlatformId: ...


class EditMessage(Protocol):
    async def __call__(self, channel_id: PlatformId, message_id: PlatformId, new_content: str): ...


class AddReaction(Protocol):
    async def __call__(self, channel_id: PlatformId, message_id: PlatformId, reaction: str): ...


class ReportError(Protocol):
    async def __call__(self, msg: str, notify_admin: bool = False): ...


class Context(Protocol):
    async def __aenter__(self): ...

    async def __aexit__(self, exc_type, exc_val, exc_tb): ...


class IndicateTyping(Protocol):
    def __call__(self, channel_id: PlatformId) -> Context: ...


class CreateThread(Protocol):
    async def __call__(self, parent_channel_id: PlatformId, title: str) -> PlatformId: ...


class ConversationComplete(BaseException):
    def __init__(self, message=None):
        super().__init__(message)


@dataclasses.dataclass
class ConcludesResponse:
    result: Any
