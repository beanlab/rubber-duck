import schedule
import time
import threading
import asyncio
from typing import Protocol, Callable
from ..utils.logger import duck_logger


class SendMessage(Protocol):
    async def __call__(self, channel_id: int, message: str) -> None: ...


class FeedbackNotifier:
    """
    A class that checks feedback queues daily and notifies channels about pending feedback
    """

    def __init__(self,
                 feedback_manager,
                 send_message: SendMessage,
                 loop: asyncio.AbstractEventLoop):
        self._feedback_manager = feedback_manager
        self._send_message = send_message
        self._running = False
        self._thread = None
        self._loop = loop
        # Schedule the job to run at 9:00 AM
        schedule.every().day.at("13:19").do(self._run_async_check_queues)

    def _run_async_check_queues(self):
        """
        Schedule the async check to run in the main event loop
        """
        asyncio.run_coroutine_threadsafe(self._check_queues(), self._loop)

    async def _check_queues(self):
        """
        Check all queues and send notifications for channels with pending feedback
        """
        duck_logger.info("Checking feedback queues for pending items")
        for channel_id, queue in self._feedback_manager._queues.items():
            duck_logger.info(f"Checking queue for channel {channel_id}")
            # Access the queue's data directly since it should be in memory
            if hasattr(queue, '_queue'):
                items = queue._queue
                duck_logger.info(f"Queue contents for channel {channel_id}: {items}")
                if items:  # If there are items
                    count = len(items)
                    message = (
                        f"📝 **Daily Feedback Check**\n"
                        f"There {'is' if count == 1 else 'are'} {count} "
                        f"conversation{'s' if count != 1 else ''} waiting for review."
                    )
                    await self._send_message(channel_id, message)
                    duck_logger.info(f"Sent notification to channel {channel_id} about {count} pending items")
                else:
                    duck_logger.info(f"No pending feedback in channel {channel_id}, skipping notification")
            else:
                duck_logger.warning(f"Queue for channel {channel_id} has no data")

    def start(self):
        """
        Start the scheduler in a background thread
        """
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_scheduler)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        """
        Stop the scheduler
        """
        self._running = False
        if self._thread:
            self._thread.join()

    def _run_scheduler(self):
        """
        Run the scheduler loop
        """
        while self._running:
            schedule.run_pending()
            time.sleep(10)  # Check every 10 seconds
