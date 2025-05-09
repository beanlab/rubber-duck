from typing import TypedDict

from ..utils.persistent_queue import PersistentQueue

CHANNEL_ID = int


class FeedbackData(TypedDict):
    duck_type: str
    guild_id: int
    parent_channel_id: int
    user_id: int
    conversation_thread_id: int


class FeedbackManager:
    def __init__(self,
                 queues: dict[CHANNEL_ID, PersistentQueue[FeedbackData]]
                 ):
        self._queues = queues

    def remember_conversation(self, feedback_data: FeedbackData):
        queue = self._queues.get(feedback_data['parent_channel_id'])
        if queue is not None:
            queue.put(feedback_data)

    def get_conversation(self, channel_id) -> FeedbackData | None:
        queue = self._queues[channel_id]
        if queue:
            return queue.pop()
        return None
