import schedule
import time
import threading
from typing import Protocol, Callable
import asyncio
from datetime import datetime, timedelta

from .config_types import ServerConfig
from ..metrics.feedback_manager import FeedbackManager
from ..utils.logger import duck_logger

class SendMessage(Protocol):
    async def __call__(self, channel_id: int, message: str) -> None: ...

class FeedbackNotifier:
    """
    A class that checks feedback queues daily and notifies channels about pending feedback
    """
    def __init__(self, 
                 feedback_manager: FeedbackManager,
                 send_message,
                 server_config: ServerConfig
                 ):
        self._feedback_manager = feedback_manager
        self._send_message: SendMessage = send_message
        self._server_config = server_config
        self._feedback_mapping = None

    async def start(self):
        """
        Starts the feedback notifier in an async context.
        Checks feedback daily at 9:00 AM.
        """
        duck_logger.info("Starting feedback notifier")
        self._build_feedback_mapping()
        
        # Run the initial check
        await self._check_feedback()
        
        while True:
            # Calculate time until next 9:00 AM
            now = datetime.now()
            next_run = now.replace(hour=16, minute=14, second=0, microsecond=0)
            if now >= next_run:
                next_run = next_run + timedelta(days=1)
            
            # Sleep until next run time
            sleep_seconds = (next_run - now).total_seconds()
            duck_logger.debug(f"Next feedback check scheduled for {next_run}")
            await asyncio.sleep(sleep_seconds)
            
            # Run the check
            await self._check_feedback()

    async def _check_feedback(self):
        """
        This function checks the feedback queues of all TA review channels and sends a notification.
        :return: None
        """
        duck_logger.debug("Checking feedback")
        if self._feedback_mapping is None:
            duck_logger.error("Feedback mapping is not initialized.")
            return
        
        for ta_channel_id, target_channels in self._feedback_mapping.items():
            total_pending = 0
            for target_channel_id in target_channels:
                length = self._feedback_manager.get_length(target_channel_id)
                total_pending += length
                duck_logger.debug(f"Target channel {target_channel_id} has {length} pending feedback items.")
            
            if total_pending > 0:
                duck_logger.debug(f"TA channel {ta_channel_id} has {total_pending} total pending feedback items.")
                message = f"There are currently {total_pending} feedback items pending review across all target channels."
                await self._send_message(ta_channel_id, message)
                
    def _build_feedback_mapping(self):
        """
        This function parses the server config and maps TA review channels to their target channels.
        Returns a dictionary where:
        - Key: TA review channel ID
        - Value: List of target channel IDs that feed into this TA review channel
        """
        self._feedback_mapping = {}
        
        for server in self._server_config:
            for channel in server['channels']:
                if channel['channel_name'] == 'ta-review':
                    ta_channel_id = channel['channel_id']
                    target_channels = []
                    
                    # Find all ducks of type conversation_review in this channel
                    for duck in channel['ducks']:
                        if duck['workflow_type'] == 'conversation_review':
                            target_channels.extend(duck['settings']['target_channel_ids'])
                    
                    if target_channels:
                        self._feedback_mapping[ta_channel_id] = target_channels
                        duck_logger.debug(f"Mapped TA channel {ta_channel_id} to {len(target_channels)} target channels")

