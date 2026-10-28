from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from .commands.command import Command
    from .gen_ai.ai_responses import ResponsesAPI
    from .utils.python_exec_container import PythonExecContainer


class MessageHandler(Protocol):
    async def send_text(self, channel_id: int, text: str): ...

    async def send_image(self, channel_id: int, filename: str, image_data: bytes): ...
    
    async def send_attachment(self, channel_id: int, filename: str, file_data: bytes): ...
    
    async def send_table(self, channel_id: int, header: list[str], rows: list[list[str]]): ...
    
    async def add_reaction(self, channel_id: int, message_id: int, emoji: str): ...

    def typing(self, channel_id): ...


class MetricsHandler(Protocol):
    async def record_message(
            self,
            guild_id: int,
            thread_id: int,
            user_id: int,
            type_: str,
            output: dict,
    ): ...

    async def record_usage(
            self,
            guild_id,
            parent_channel_id,
            thread_id,
            user_id,
            engine,
            input_tokens,
            output_tokens,
            cached_tokens=None,
            reasoning_tokens=None,
    ): ...

    async def record_feedback(
            self,
            workflow_type: str,
            guild_id: int,
            parent_channel_id: int,
            thread_id: int,
            user_id: int,
            reviewer_id: int,
            feedback_score: int,
            written_feedback: str,
    ): ...


@dataclass
class DuckContext:
    guild_id: int
    parent_channel_id: int
    author_id: int
    author_mention: str
    content: str
    message_id: int
    thread_id: int
    timeout: int


class DuckConversation(Protocol):
    """
    A duck workflow.
    The same instance will be invoked repeatedly for each
    conversation instance.
    """
    name: str
    commands: list["Command"]

    async def __call__(self, context: DuckContext): ...


class DuckBuilder(Protocol):
    def __call__(
            self,
            name: str,
            settings: dict,
            *,
            message_handler: MessageHandler,
            metrics_handler: MetricsHandler,
            responses_api: "ResponsesAPI",
            containers: dict[str, "PythonExecContainer"],
            sql_session: "Session",
            tool_configs: dict,
    ) -> DuckConversation: ...
