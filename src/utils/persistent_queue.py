import asyncio

from quest import PersistentHistory
from quest.extras.sql import SqlBlobStorage


class PersistentQueue:
    def __init__(self, channel_id: int, session):
        # Use the provided SQL session
        self._storage = SqlBlobStorage(f'{channel_id}', session)
        self._history = PersistentHistory(namespace=f"queue-{channel_id}", storage=self._storage)
        self._queue = asyncio.Queue()
        self.channel_id = channel_id

        # Restore queue state from history
        if self._history:
            last_state = self._history[-1]  # Get the last saved state
            if last_state['type'] == 'queue_state':
                for item in last_state['state']:
                    self._queue.put_nowait(item)

    def get_channel_id(self):
        return self.channel_id

    async def put(self, item):
        await self._queue.put(item)

    async def get(self):
        return await self._queue.get()

    def is_empty(self) -> bool:
        # Check if the queue is empty
        return self._queue.empty()

    def stash_state(self):
        # Save the current queue state to history
        state = []
        while not self._queue.empty():
            state.append(self._queue.get_nowait())
        self._history.append({'type': 'queue_state', 'state': state})

        # Rehydrate the queue with the saved state
        for item in state:
            self._queue.put_nowait(item)

    def clear(self):
        self._history.clear()
        while not self._queue.empty():
            self._queue.get_nowait()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Automatically stash the state when exiting
        self.stash_state()
