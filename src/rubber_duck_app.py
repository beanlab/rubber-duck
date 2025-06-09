from quest import WorkflowManager

from .utils.config_types import ChannelConfig, DuckContext
from .utils.logger import duck_logger
from .utils.protocols import Message


class RubberDuckApp:
    def __init__(self, admin_channel_id: int, channel_configs: dict[int, ChannelConfig], workflow_manager):
        self._admin_channel = admin_channel_id
        self._workflow_manager: WorkflowManager = workflow_manager
        self._channel_configs = channel_configs

    def _make_context(self, message: Message) -> DuckContext:
        return DuckContext(
            guild_id=message['guild_id'],
            channel_id=message['channel_id'],
            author_id=message['author_id'],
            author_mention=message['author_mention'],
            content=message['content'],
            message_id=message['message_id'],
            thread_id=None
        )

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
            context = self._make_context(message)
            workflow_id = f'duck-{message["channel_id"]}-{message["message_id"]}'
            self._workflow_manager.start_workflow(
                'duck-orchestrator',
                workflow_id,
                context
            )
            return

        # Belongs to an existing conversation
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