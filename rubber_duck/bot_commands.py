from rubber_duck import Message
from quest import step
from command import Command


class BotCommands:
    def __init__(self, commands: {}):
        self.commands = commands

    async def __call__(self, message: Message):
        return await self.handle_command(message)

    async def handle_command(self, message: Message):
        # Extract the command from the content
        content = message['content']
        command_name = content.split()[0]
        # Get the corresponding class
        command_class = self.commands[command_name]
        await command_class.execute(message)
