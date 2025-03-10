from command import Command
from rubber_duck import Message

class BotCommands:
    def __init__(self, commands: list[Command], send_message):
        self.commands = {command.name: command for command in commands}
        self.send_message = send_message

    async def __call__(self, message: Message):
        return await self.handle_command(message)

    async def get_help(self, channel_id):
        help_string = "!help - print out this message\n"

        for command in self.commands.values():
            help_string += command.help_msg

        wrap_help_string = f"```\n{help_string}\n```"

        await self.send_message(channel_id, wrap_help_string)

    async def handle_command(self, message: Message):
        # Extract the command from the content
        content = message['content']
        command_name = content.split()[0]

        # Send help message
        if command_name == "!help":
            await self.get_help(message['channel_id'])

        # Get the corresponding class and execute
        elif command_name in self.commands:
            command_class = self.commands[command_name]
            await command_class.execute(message)
        # Send unknown message
        else:
            await self.send_message(message['channel_id'], 'Unknown command. Try !help')
