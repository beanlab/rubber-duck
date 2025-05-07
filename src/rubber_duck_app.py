from utils.config_types import ChannelConfig
from .utils.protocols import Message


class RubberDuckApp:
    def __init__(self, channel_configs: dict[int, ChannelConfig], workflow_manager):
        self._workflow_manager = workflow_manager
        self._channel_configs = channel_configs

    async def route_message(self, message: Message):
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

        # Belongs to an existing conversation
        str_id = str(message["channel_id"])
        if self._workflow_manager.has_workflow(str_id):
            await self._workflow_manager.send_event(
                str_id, 'messages', None, 'put',
                message
            )

        # If it didn't match anything above, we can ignore it.

    async def route_reaction(self, emoji, message_id, user_id):
        workflow_alias = str(message_id)

        if self._workflow_manager.has_workflow(workflow_alias):
            await self._workflow_manager.send_event(
                workflow_alias, 'feedback', None, 'put',
                (emoji, user_id)
            )
