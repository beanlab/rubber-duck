from utils.config_types import ChannelConfig


class FeedbackManager():
    def __init__(self, server_id: int, queue: PersistentQueue):
        self._server_id = server_id
        self._queue = queue

    def remember_conversation(self, channel_config: ChannelConfig, thread_id: int):
        channel_id = channel_config["channel_id"]
        if channel_config["feedback"]:
            link = f"https://discord.com/channels/{self._server_id}/{channel_id}/{thread_id}"
            self._queue.put(link)

    def get_conversation(self) -> str | None:
        # Get the conversation link from the queue
        if not self._queue.empty():
            return self._queue.get()
        return None
