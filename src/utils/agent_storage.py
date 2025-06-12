from quest import BlobStorage


class LastAgentStorage:
    def __init__(self, storage_key: str, blob_storage: BlobStorage):
        # Use the provided SQL session
        self._storage = blob_storage
        self._storage_key = storage_key

    def _stash(self):
        self._storage.write_blob(self._storage_key, self._last_agent)

    def __enter__(self):
        self._last_agent = self._storage.read_blob(self._storage_key) or ""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stash()

    def set(self, agent: str):
        self._last_agent = agent

    def get(self) -> str:
        return self._last_agent

