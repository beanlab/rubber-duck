from quest import BlobStorage


class LastAgentStorage:
    def __init__(self, namespace: str, blob_storage: BlobStorage):
        self._storage = blob_storage
        self._namespace = namespace
        self._last_agent = {}

    def _stash(self):
        self._storage.write_blob(self._namespace, self._last_agent)

    def __enter__(self):
        self._last_agent = self._storage.read_blob(self._namespace) or {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stash()

    def set(self, thread_id, agent: str):
        self._last_agent[thread_id] = agent

    def get(self, thread_id: int) -> str:
        return self._last_agent[thread_id]

