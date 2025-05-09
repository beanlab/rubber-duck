from ..utils.persistent_queue import PersistentQueue

CHANNEL_ID = int


class FeedbackManager:
    def __init__(self,
                 queues: dict[CHANNEL_ID, PersistentQueue]
                 ):
        self._queues = queues

    def remember_conversation(self, channel_id: int, thread_id: int):
        queue = self._queues.get(channel_id)
        if queue is not None:
            queue.put(thread_id)

    async def get_conversation(self, channel_id) -> int | None:
        queue = self._queues[channel_id]
        if queue:
            return queue.pop()
        return None
