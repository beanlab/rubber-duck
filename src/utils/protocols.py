import dataclasses
from typing import Protocol, TypedDict, Any, TYPE_CHECKING

from .python_exec_container import FileResult
from ..utils.config_types import FileData

if TYPE_CHECKING:
    from ..armory.tool_cache import CacheKey


class Attachment(TypedDict):
    attachment_id: int
    description: str
    filename: str
    size: int
    url: str


class Message(TypedDict):
    guild_id: int
    channel_name: str
    channel_id: int
    author_id: int
    author_name: str
    author_mention: str
    message_id: int
    content: str
    files: list[Attachment]


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


class ConversationComplete(BaseException):
    def __init__(self, message=None):
        super().__init__(message)


class ToolCache(Protocol):
    def check_if_cached(self, cache_key: "CacheKey") -> bool:
        ...

    async def send_from_cache(self, cache_key: "CacheKey", send_message: SendMessage, channel_id: int) -> dict[
        str, Any]:
        ...

    def cache_file(self, cache_key: "CacheKey", filename: str, file: FileResult) -> None:
        ...

    def cache_table(self, cache_key: "CacheKey", table_chunks: list[str]) -> None:
        ...

    def cache_msg(self, cache_key: "CacheKey", msg: str) -> None:
        ...


class CacheKeyBuilder(Protocol):
    def build_cache_key(self, last_3_messages: str, code: str) -> "CacheKey":
        ...


@dataclasses.dataclass
class ConcludesResponse:
    result: Any
