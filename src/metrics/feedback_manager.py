from typing import TypedDict

from ..utils.config_types import CHANNEL_ID
from ..utils.logger import duck_logger
from ..utils.persistent_queue import PersistentQueue


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
        duck_logger.info(f"Initialized FeedbackManager with queues for channels: {list(queues.keys())}")

    def remember_conversation(self, feedback_data: FeedbackData):
        queue = self._queues.get(feedback_data['parent_channel_id'])
        if queue is not None:
            duck_logger.info(
                f"Remembering conversation for channel {feedback_data['parent_channel_id']}: {feedback_data}")
            queue.put(feedback_data)
        else:
            duck_logger.warning(f"No queue found for channel {feedback_data['parent_channel_id']}")

    async def get_conversation(self, channel_id) -> FeedbackData | None:
        # Must be async to work with quest.step
        queue = self._queues.get(channel_id)
        if queue:
            data = queue.pop()
            duck_logger.info(f"Retrieved conversation for channel {channel_id}: {data}")
            return data

        duck_logger.warning(f"No queue found for channel {channel_id} (could be empty)")
        return None

    def get_length(self, channel_id: CHANNEL_ID) -> int:
        queue = self._queues.get(channel_id)
        if queue:
            length = len(queue._queue)
            duck_logger.info(f"Queue length for channel {channel_id}: {length}")
            return length
        duck_logger.warning(f"No queue found for channel {channel_id}")
        return 0
