from quest.persistence import BlobStorage


class PersistentQueue:
    def __init__(self, storage_key: str, blob_storage: BlobStorage):
        # Use the provided SQL session
        self._storage = blob_storage
        self._storage_key = storage_key
        self._queue = []

    def _stash(self):
        self._storage.write_blob(self._storage_key, self._queue)

    async def __aenter__(self):
        # Rehydrate my data
        self._queue = self._storage.read_blob(self._storage_key)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._stash()

    def put(self, item):
        self._queue.append(item)

    def pop(self):
        return self._queue.pop(0)

    def __bool__(self) -> bool:
        # Check if the queue is empty
        return bool(self._queue)
