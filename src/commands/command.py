import io
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

import discord
import pytz
from quest import step
from quest.manager import find_workflow_manager

from ..utils.logger import duck_logger
from ..utils.protocols import Message
from ..utils.zip_utils import zip_data_file


class Command:
    name = ""
    help_msg = ""

    async def execute(self, message: Message):
        pass


class MessagesMetricsCommand(Command):
    name = "!messages"
    help_msg = "get a zip of the messages data"

    def __init__(self, send_message, metrics_handler):
        self.send_message = send_message
        self.metrics_handler = metrics_handler

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        messages_zip = zip_data_file(self.metrics_handler.get_messages())
        discord_messages_file = discord.File(messages_zip, filename="messages.zip")
        await self.send_message(channel_id, "", file=discord_messages_file)


class UsageMetricsCommand(Command):
    name = "!usage"
    help_msg = "get a zip of the usage data"

    def __init__(self, send_message, metrics_handler):
        self.send_message = send_message
        self.metrics_handler = metrics_handler

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        usage_zip = zip_data_file(self.metrics_handler.get_usage())
        discord_usage_file = discord.File(usage_zip, filename="usage.zip")
        await self.send_message(channel_id, "", file=discord_usage_file)


class FeedbackMetricsCommand(Command):
    name = "!feedback"
    help_msg = "get a zip of the feedback data"

    def __init__(self, send_message, metrics_handler):
        self.send_message = send_message
        self.metrics_handler = metrics_handler

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        feedback_zip = zip_data_file(self.metrics_handler.get_feedback())
        discord_feedback_file = discord.File(feedback_zip, filename="feedback.zip")
        await self.send_message(channel_id, "", file=discord_feedback_file)


class MetricsCommand(Command):
    name = "!metrics"
    help_msg = "get the zips of the data tables"

    def __init__(self, messages_metrics: MessagesMetricsCommand, usage_metrics: UsageMetricsCommand,
                 feedback_metrics: FeedbackMetricsCommand):
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
    help_msg = "print a status message"

    def __init__(self, send_message):
        self.send_message = send_message

    async def execute(self, message: Message):
        channel_id = message['channel_id']
        await self.send_message(channel_id, 'I am alive. 🦆')

class ReportCommand(Command):
    name = "!report"
    help_msg = "get the report"

    def __init__(self, send_message, reporter):
        self.send_message = send_message
        self.reporter = reporter

    @step
    async def execute(self, message: Message):
        """ Execute the report command to generate and send a report based on the message content."""
        try:
            content = message['content']
            channel_id = message['channel_id']
            if content in ['!report', '!report help', '!report h']:
                help_text = self.reporter.help_menu()
                await self.send_message(channel_id, help_text)
            else:
                result = self.reporter.get_report(content)

                if result is None:
                    await self.send_message(channel_id, "No data available")
                elif isinstance(result, str):  # Help text or error message
                    await self.send_message(channel_id, result)
                else:  # List of (title, image) tuples
                    for title, image in result:
                        file = discord.File(fp=image, filename=title)
                        await self.send_message(channel_id, "", file=file)
        except Exception as e:
            duck_logger.error(f"Error executing report command: {e}")
            channel_id = message['channel_id']
            await self.send_message(channel_id, f"An error occurred while generating the report: {e}")
            raise


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


class LogCommand(Command):
    """
    This command is used to get the log file.
    It will zip all the log files and send them to the channel.
    """
    name = "!log"
    help_msg = "get the log file"

    def __init__(self, send_message, log_dir: Path = None):
        self.send_message = send_message
        self.log_dir = log_dir

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']

        # Check if logs directory exists
        if not self.log_dir.exists():
            await self.send_message(channel_id, 'No logs directory found.')
            return

        # Get the .log files in the logs directory
        log_files = list(self.log_dir.glob('*.log*'))
        if not log_files:
            await self.send_message(channel_id, 'No log files found.')
            return

        # Create in-memory zip buffer
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in log_files:
                zipf.write(file, arcname=file.name)

        # Move the buffer pointer to the start
        zip_buffer.seek(0)

        try:
            # Create Discord file from the zip buffer
            filename = f'logs_{datetime.now().strftime("%Y_%m_%d_%H_%M")}.zip'
            discord_file = discord.File(zip_buffer, filename=filename)

            # Send the zip file to the specified channel
            await self.send_message(channel_id, 'Here are the log files:')
            await self.send_message(channel_id, "", file=discord_file)

        except Exception as e:
            await self.send_message(channel_id, f'Error sending log files: {str(e)}')

        finally:
            zip_buffer.close()


class ActiveWorkflowsCommand(Command):
    name = "!active"
    help_msg = "get the active workflow metrics"

    def __init__(self, send_message, get_workflow_metrics):
        self.send_message = send_message
        self.get_workflow_metrics = get_workflow_metrics

    async def _execute_summary(self, message: Message):
        channel_id = message['channel_id']
        active_workflows = self.get_workflow_metrics()

        counts = {}
        for metric in active_workflows:
            wtype = metric['workflow_type']
            counts[wtype] = counts.get(wtype, 0) + 1

        msg = '\n'.join(f'Type: {wtype}\nCount: {count}\n' for wtype, count in counts.items())

        await self.send_message(channel_id, f"```\nActive Workflows:\n{msg}```")

    async def _execute_full(self, message: Message):
        channel_id = message['channel_id']
        active_workflows = self.get_workflow_metrics()

        msg = ""
        count = 0
        for metric in active_workflows:
            count += 1
            start_time = metric['start_time']
            # Convert to datetime object (UTC)
            dt_utc = datetime.fromisoformat(start_time).replace(tzinfo=pytz.utc)

            # Convert to Mountain Time
            mountain_time_zone = pytz.timezone("America/Denver")
            dt_mountain = dt_utc.astimezone(mountain_time_zone)

            # Get the time zone string
            time_zone_str = dt_mountain.strftime("%Z")

            # Reformat string to be more readable
            formatted_time = dt_mountain.strftime("%m-%d-%Y %I:%M:%S %p")
            msg += (
                f"Workflow {count}\n"
                f"ID: {metric['workflow_id']}\n"
                f"Type: {metric['workflow_type']}\n"
                f"Start Time ({time_zone_str}): {formatted_time}\n\n"
            )

        await self.send_message(channel_id, f"```\n{msg}```")

    @step
    async def execute(self, message: Message):
        if 'full' in message['content']:
            await self._execute_full(message)
        else:
            await self._execute_summary(message)


def create_commands(send_message, metrics_handler, reporter, log_dir) -> list[Command]:
    # Create and return the list of commands
    def get_workflow_metrics():
        return find_workflow_manager().get_workflow_metrics()

    return [
        messages := MessagesMetricsCommand(send_message, metrics_handler),
        usage := UsageMetricsCommand(send_message, metrics_handler),
        feedback := FeedbackMetricsCommand(send_message, metrics_handler),
        MetricsCommand(messages, usage, feedback),
        StatusCommand(send_message),
        ReportCommand(send_message, reporter),
        LogCommand(send_message, log_dir),
        ActiveWorkflowsCommand(send_message, get_workflow_metrics)
    ]
