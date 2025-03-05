from rubber_duck import Message
from quest import step
from command import Command


class BotCommands:
    def __init__(self, send_message, metrics_handler, reporter):
        self._send_message = step(send_message)
        self._metrics_handler = metrics_handler
        self._reporter = reporter

    async def __call__(self, message: Message):
        return await self.handle_command(message)

    async def handle_command(self, message: Message):
        content = message['content']
        channel_id = message['channel_id']

        # Extract the command
        command_name = content.split()[0]
        # Get the corresponding class
        command_class = Command.get_command(command_name)

        # Instantiate and execute the command
        command_instance = command_class(self._send_message, self._metrics_handler, self._reporter)
        await command_instance.execute(content, channel_id)
