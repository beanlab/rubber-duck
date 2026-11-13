from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationThread:
    guild_id: int
    user_id: int
    entry_channel_id: int
    thread_id: int
