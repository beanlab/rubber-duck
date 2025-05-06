from duck_orchestrator import DuckOrchestrator
from .utils.protocols import Message
from .utils.config_types import ServerConfig


class RubberDuckApp:
    def __init__(self, server_configs: dict[str, ServerConfig], command_channel: int, workflow_manager):
        self._command_channel = command_channel
        self._workflow_manager = workflow_manager
        self._orchestrator = DuckOrchestrator(server_configs, workflow_manager)

        # Collect all duck channel IDs across all servers
        self._duck_channels = {
            channel["channel_id"]
            for server in server_configs.values()
            for channel in server["channels"]
        }

    async def route_message(self, message: Message):
        # Command channel
        if message['channel_id'] == self._command_channel:
            workflow_id = f'command-{message["message_id"]}'
            # TODO make a workflow for commands?
            self._workflow_manager.start_workflow(
                'command', workflow_id, message)
            return

        # Duck channel
        if message['channel_id'] in self._duck_channels:
            # Call DuckOrchestrator
            workflow_id = f'duck-{message["channel_id"]}-{message["message_id"]}'
            self._workflow_manager.start_workflow(
                'duck-orchestra',
                workflow_id,
                message['channel_id'],
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

