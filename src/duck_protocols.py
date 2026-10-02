from dataclasses import dataclass
from typing import Protocol

from src.commands.command import Command
from src.gen_ai.ai_responses import ResponsesAPI
from src.metrics.feedback_manager import FeedbackManager


class MessageHandler(Protocol):
    def send_message(self): ...

    def on_reaction(self): ...

    def typing(self): ...


class MetricsHandler(Protocol):
    async def record_message(self, guild_id: int, thread_id: int, user_id: int, type_: str, output: dict):
        ...

    async def record_usage(self, guild_id, parent_channel_id, thread_id, user_id, engine, input_tokens, output_tokens,
                           cached_tokens=None, reasoning_tokens=None):
        ...

    async def record_feedback(self, workflow_type: str, guild_id: int, parent_channel_id: int, thread_id: int,
                              user_id: int, reviewer_id: int,
                              feedback_score: int, written_feedback: str):
        ...


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
    The same instance will be invoked repeated for each
    conversation instance.
    """
    name: str
    commands: list[Command]

    async def run_conversation(self, context: DuckContext): ...


class DuckBuilder(Protocol):
    def __call__(
            self,
            settings: dict,
            message_handler: MessageHandler,
            metrics_handler: MetricsHandler,
            feedback_manager: FeedbackManager,
            responses_api: ResponsesAPI
    ) -> DuckConversation:
        ...
