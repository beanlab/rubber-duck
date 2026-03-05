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
    def cleanup(self):
        ...

    def get_key_hash(self, cache_key: "CacheKey") -> str:
        ...

    def check_if_cached(self, key_hash: str) -> bool:
        ...

    async def send_from_cache(self, key_hash: str, send_message: SendMessage, channel_id: int) -> dict[
        str, Any]:
        ...

    def cache_file(self, key_hash: str, filename: str, file: FileResult):
        ...

    def cache_table(self, key_hash: str, filename: str, table_chunks: list[str], description: str = ""):
        ...

    def cache_msg(self, key_hash: str, msg: str):
        ...


class CacheKeyBuilder(Protocol):
    def build_cache_key(self, user_intent: str, code: str) -> "CacheKey":
        ...


@dataclasses.dataclass
class ConcludesResponse:
    result: Any
