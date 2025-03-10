import discord
import reporter
import subprocess

from pathlib import Path
from quest import step
from protocols import Message


class Command():
    name = ""
    help_msg = ""

    async def execute(self, message: Message):
        pass


class MessagesMetricsCommand(Command):
    name = "!messages"
    help_msg = "!messages - get a zip of the messages data\n"

    def __init__(self, send_message, metrics_handler):
        self.send_message = send_message
        self.metrics_handler = metrics_handler

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        messages_zip = reporter.zip_data_file(self.metrics_handler.get_messages())
        discord_messages_file = discord.File(messages_zip, filename="messages.zip")
        await self.send_message(channel_id, "", file=discord_messages_file)


class UsageMetricsCommand(Command):
    name = "!usage"
    help_msg = "!usage - get a zip of the usage data\n"

    def __init__(self, send_message, metrics_handler):
        self.send_message = send_message
        self.metrics_handler = metrics_handler

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        usage_zip = reporter.zip_data_file(self.metrics_handler.get_usage())
        discord_usage_file = discord.File(usage_zip, filename="usage.zip")
        await self.send_message(channel_id, "", file=discord_usage_file)


class FeedbackMetricsCommand(Command):
    name = "!feedback"
    help_msg = "!feedback - get a zip of the feedback data\n"

    def __init__(self, send_message, metrics_handler):
        self.send_message = send_message
        self.metrics_handler = metrics_handler

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        feedback_zip = reporter.zip_data_file(self.metrics_handler.get_feedback())
        discord_feedback_file = discord.File(feedback_zip, filename="feedback.zip")
        await self.send_message(channel_id, "", file=discord_feedback_file)


class MetricsCommand(Command):
    name = "!metrics"
    help_msg = "!metrics - get the zips of the data tables\n"

    def __init__(self, messages_metrics: MessagesMetricsCommand, usage_metrics: UsageMetricsCommand, feedback_metrics: FeedbackMetricsCommand):
        self.messages_metrics = messages_metrics
        self.usage_metrics = usage_metrics
        self.feedback_metrics = feedback_metrics

    @step
    async def execute(self, message: Message):
        await self.messages_metrics.execute(message)
        await self.usage_metrics.execute(message)
        await self.feedback_metrics.execute(message)


class StatusCommand(Command):
    name = "!status"
    help_msg = "!status - print a status message\n"

    def __init__(self, send_message):
        self.send_message = send_message

    async def execute(self, message: Message):
        channel_id = message['channel_id']
        await self.send_message(channel_id, 'I am alive. 🦆')


class ReportCommand(Command):
    name = "!report"
    help_msg = "!report - get the report\n"

    def __init__(self, send_message, reporter):
        self.send_message = send_message
        self.reporter = reporter

    @step
    async def execute(self, message: Message):
        content = message['content']
        channel_id = message['channel_id']
        img_name, img = self.reporter.get_report(content)
        if img is None:
            await self.send_message(channel_id, img_name)

        elif isinstance(img, list):
            imgs = [discord.File(fp=image, filename=image_name) for image, image_name in zip(img, img_name)]
            await self.send_message(channel_id, img_name, files=imgs)

        else:
            await self.send_message(channel_id, img_name, file=discord.File(fp=img, filename=img_name))


class BashExecuteCommand():
    def __init__(self, send_message):
        self.send_message = send_message

    @step
    async def run(self, command):
        work_dir = Path(__file__).parent
        process = subprocess.run(
            command,
            shell=isinstance(command, str), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir
        )
        return process.stdout.decode('utf-8'), process.stderr.decode('utf-8')

    @step
    async def execute_command(self, channel_id, text):
        """
        Execute a command in the shell and return the output to the channel
        """
        # Run command using shell and pipe output to channel
        await self.send_message(channel_id, f"```bash\n$ {text}```")
        output, errors = await self.run(text)

        if errors:
            await self.send_message(channel_id, f'Errors: ```{errors}```')

        if output:
            await self.send_message(channel_id, f'```{output}```')


class StateCommand(Command):
    name = "!state"
    help_msg = "!state - get a zip of the state folder\n"

    def __init__(self, send_message, bash_execute_command: BashExecuteCommand):
        self.send_message = send_message
        self.bash_execute_command = bash_execute_command

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        await self.send_message(channel_id, "Getting state zip")
        await self.bash_execute_command.execute_command(channel_id, 'zip -q -r state.zip state')
        await self.send_message(channel_id, 'state zip', file='state.zip')


class LogCommand(Command):
    name = "!log"
    help_msg = "!log - get the log file\n"

    def __init__(self, send_message, bash_execute_command: BashExecuteCommand):
        self.send_message = send_message

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        await self.send_message(channel_id, 'The log command has been temporarily disabled.')
        #await self.bash_execute_command(channel_id, f'zip -q -r log.zip {self._log_file_path}')
        #await self._send_message(channel_id, 'log zip', file='log.zip')
