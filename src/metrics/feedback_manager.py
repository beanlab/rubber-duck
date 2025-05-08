from utils.config_types import ChannelConfig
from utils.persistent_queue import PersistentQueue


class FeedbackManager:
    def __init__(self, queues: dict[int, PersistentQueue]):
        self._queues = queues

    def remember_conversation(self, server_id: int, channel_config: ChannelConfig, thread_id: int):
        channel_id = channel_config["channel_id"]
        queue = self._queues[channel_id]
        if channel_config["feedback"]:
            link = f"https://discord.com/channels/{server_id}/{channel_id}/{thread_id}"
            queue.put(link)

    async def get_conversation(self, channel_id) -> str | None:
        # Get the conversation link from the queue
        queue = self._queues[channel_id]
        if not queue.is_empty():
            return await queue.get()
        return None
