import datetime
import discord
import re
import reporter
import subprocess

from abc import abstractmethod, ABC
from pathlib import Path
from quest import step


class Command(ABC):
    # Stores all command classes
    _registry = {}

    def __init__(self, send_message, metrics_handler, reporter):
        self._send_message = send_message
        self._metrics_handler = metrics_handler
        self._reporter = reporter

    # Abstract method that each class will implement
    @abstractmethod
    async def execute(self, content: str, channel_id: int):
        pass

    # Register a command class
    @classmethod
    def register(cls, command_name):
        # Decorator to register a command with a specific name.
        def wrapper(subclass):
            cls._registry[command_name] = subclass
            return subclass
        return wrapper

    # Get a command by its name
    @classmethod
    def get_command(cls, name):
        #Returns the command class if it exists, or it returns the UnknownCommand
        return cls._registry.get(name, UnknownCommand)

    @step
    async def _run(self, command):
        work_dir = Path(__file__).parent
        process = subprocess.run(
            command,
            shell=isinstance(command, str), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir
        )
        return process.stdout.decode('utf-8'), process.stderr.decode('utf-8')

    @step
    async def _execute_command(self, channel_id, text):
        """
        Execute a command in the shell and return the output to the channel
        """
        # Run command using shell and pipe output to channel
        await self._send_message(channel_id, f"```bash\n$ {text}```")
        output, errors = await self._run(text)

        if errors:
            await self._send_message(channel_id, f'Errors: ```{errors}```')

        if output:
            await self._send_message(channel_id, f'```{output}```')


@Command.register("!log")
class LogCommand(Command):
    @step
    async def execute(self, content: str, channel_id: int):
        await self._send_message(channel_id, 'The log command has been temporarily disabled.')
        #await self._execute_command(channel_id, f'zip -q -r log.zip {self._log_file_path}')
        #await self._send_message(channel_id, 'log zip', file='log.zip')


@Command.register("!metrics")
class MetricsCommand(Command):
    @step
    async def execute(self, content: str, channel_id: int):
        messages_zip = reporter.zip_data_file(self._metrics_handler.get_messages())
        usage_zip = reporter.zip_data_file(self._metrics_handler.get_usage())
        feedback_zip = reporter.zip_data_file(self._metrics_handler.get_feedback())

        discord_messages_file = discord.File(messages_zip, filename="messages.zip")
        discord_usage_file = discord.File(usage_zip, filename="usage.zip")
        discord_feedback_file = discord.File(feedback_zip, filename="feedback.zip")

        await self._send_message(channel_id, "", file=discord_messages_file)
        await self._send_message(channel_id, "", file=discord_usage_file)
        await self._send_message(channel_id, "", file=discord_feedback_file)


@Command.register("!status")
class StatusCommand(Command):
    async def execute(self, content: str, channel_id: int):
        await self._send_message(channel_id, 'I am alive. 🦆')


@Command.register("!help")
class HelpCommand(Command):
    async def execute(self, content: str, channel_id: int):
        commands_list = "\n".join(Command._registry.keys())  # Get all registered commands
        help_message = f"```\n{commands_list}\n```"
        await self._send_message(channel_id, help_message)
        # "!status - print a status message\n"
        # "!help - print this message\n"
        # "!log - get the log file\n"
        # "!metrics - get the zips of the data tables\n"
        # "!state - get a zip of the state folder\n"
        # "!restart - restart the bot\n"
        # "!clean-restart - wipe the state and restart the bot\n"


@Command.register("!report")
class ReportCommand(Command):
    @step
    async def execute(self, content: str, channel_id: int):
        img_name, img = self._reporter.get_report(content)
        if img is None:
            await self._send_message(channel_id, img_name)

        elif isinstance(img, list):
            imgs = [discord.File(fp=image, filename=image_name) for image, image_name in zip(img, img_name)]
            await self._send_message(channel_id, img_name, files=imgs)

        else:
            await self._send_message(channel_id, img_name, file=discord.File(fp=img, filename=img_name))


@Command.register("!state")
class StateCommand(Command):
    @step
    async def execute(self, content: str, channel_id: int):
        await self._send_message(channel_id, "Getting state zip")
        await self._execute_command(channel_id, 'zip -q -r state.zip state')
        await self._send_message(channel_id, 'state zip', file='state.zip')


class UnknownCommand(Command):
    async def execute(self, content: str, channel_id: int):
        await self._send_message(channel_id, 'Unknown command. Try !help')



