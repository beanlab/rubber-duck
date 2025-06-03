from typing import Protocol, Callable
import asyncio
from datetime import datetime, timedelta

from .config_types import FeedbackNotifierSettings, ServerConfig
from .protocols import SendMessage
from ..metrics.feedback_manager import FeedbackManager
from ..utils.logger import duck_logger

class FeedbackNotifier:
    """
    A class that checks feedback queues daily and notifies channels about pending feedback
    """
    def __init__(self, 
                 feedback_manager: FeedbackManager,
                 send_message,
                 server_config: ServerConfig,
                 feedback_notifier_settings: FeedbackNotifierSettings
                 ):
        self._feedback_manager = feedback_manager
        self._send_message: SendMessage = send_message
        self._server_config = server_config
        self._feedback_mapping = self._build_feedback_mapping()
        self._feedback_check_hour = feedback_notifier_settings['feedback_check_hour']
        self._feedback_check_minute = feedback_notifier_settings['feedback_check_minute']


    async def start(self):
        """
        Starts the feedback notifier in an async context.
        Checks feedback daily at 9:00 AM.
        """
        duck_logger.info("Starting feedback notifier")
        
        while True:
            # Calculate time until next 9:00 AM
            now = datetime.now()
            next_run = now.replace(hour=self._feedback_check_hour, minute=self._feedback_check_minute, second=0, microsecond=0)
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
        feedback_mapping = {}
        
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
                        feedback_mapping[ta_channel_id] = target_channels
                        duck_logger.debug(f"Mapped TA channel {ta_channel_id} to {len(target_channels)} target channels")

        return feedback_mapping