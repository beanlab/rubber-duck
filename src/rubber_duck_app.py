from quest import WorkflowManager

from .utils.config_types import ChannelConfig
from .utils.logger import duck_logger
from .utils.protocols import Message


class RubberDuckApp:
    def __init__(self, admin_channel_id: int, channel_configs: dict[int, ChannelConfig],
                 workflow_manager, conversations):
        self._admin_channel = admin_channel_id
        self._workflow_manager: WorkflowManager = workflow_manager
        self._channel_configs = channel_configs
        self._conversations = conversations

    async def route_message(self, message: Message):
        if message['channel_id'] == self._admin_channel:
            self._workflow_manager.start_workflow(
                'command',
                f'command-{message["channel_id"]}-{message["message_id"]}',
                message
            )
            return

        # Duck channel
        if message['channel_id'] in self._channel_configs:
            # Call DuckOrchestrator
            workflow_id = f'duck-{message["channel_id"]}-{message["message_id"]}'
            self._workflow_manager.start_workflow(
                'duck-orchestrator',
                workflow_id,
                self._channel_configs[message['channel_id']],
                message
            )
            return

        # Belongs to an existing conversation
        conversation = self._conversations.get_by_thread(message['channel_id'])
        if conversation is None or conversation.user_id != message['author_id']:
            return

        str_id = str(message["channel_id"])
        if self._workflow_manager.has_workflow(str_id):
            duck_logger.debug(f"Existing conversation message: {message}")
            await self._workflow_manager.send_event(
                str_id, 'messages', None, 'put',
                message
            )
            return

        # If it didn't match anything above, we can ignore it.

    async def route_reaction(self, emoji, message_id, user_id):
        workflow_alias = str(message_id)
        duck_logger.debug(f"Processing reaction: {emoji} from user {user_id} on message {message_id}")

        if self._workflow_manager.has_workflow(workflow_alias):
            await self._workflow_manager.send_event(
                workflow_alias, 'feedback', None, 'put',
                (emoji, user_id)
            )
