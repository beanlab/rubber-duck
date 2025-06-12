import subprocess
from datetime import datetime
from pathlib import Path

import discord
import pytz
from quest import step
from quest.manager import find_workflow_manager

from ..storage.sql_metrics import SQLMetricsHandler, MessagesModel, UsageModel, FeedbackModel
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
            if content == '!report help' or content == '!report h':
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
    name = "!log"
    help_msg = "get the log file"

    def __init__(self, send_message, bash_execute_command: BashExecuteCommand):
        self.send_message = send_message

    @step
    async def execute(self, message: Message):
        channel_id = message['channel_id']
        await self.send_message(channel_id, 'The log command has been temporarily disabled.')
        # await self.bash_execute_command(channel_id, f'zip -q -r log.zip {self._log_file_path}')
        # await self._send_message(channel_id, 'log zip', file='log.zip')


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


class MigrateTableCommand(Command):
    """Command to migrate a table to a new schema by renaming columns."""
    name = "!migrate"
    help_msg = "migrate a table to a new schema. Usage: !migrate <table_name> [old_col=new_col ...]"

    def __init__(self, send_message, metrics_handler):
        self.send_message = send_message
        self.metrics_handler = metrics_handler

    @step
    async def execute(self, message: Message):
        try:
            content = message['content'].split()
            if len(content) < 3:
                help_text = "Usage: !migrate <table_name> [old_col=new_col ...]"
                await self.send_message(message['channel_id'], help_text)
                duck_logger.warning(f"Usage: !migrate <table_name> [old_col=new_col ...]")
                return

            table_name = content[1]
            
            # Parse renamed columns from arguments
            renamed_columns = {}
            for arg in content[2:]:
                if '=' in arg:
                    new_col, old_col = arg.split('=')
                    renamed_columns[new_col] = old_col

            # Map table name to model
            model_map = {
                'messages': MessagesModel,
                'usage': UsageModel,
                'feedback': FeedbackModel
            }

            if table_name not in model_map:
                await self.send_message(
                    message['channel_id'], 
                    f"Invalid table name. Must be one of: {', '.join(model_map.keys())}"
                )
                return

            # Perform migration
            SQLMetricsHandler.alter_table(
                self.metrics_handler.session,
                model_map[table_name],
                renamed_columns
            )
            
            await self.send_message(
                message['channel_id'], 
                f"Successfully altered table '{table_name}' with the following changes: {renamed_columns}"
            )

            duck_logger.info(
                f"Successfully altered table '{table_name}' with the following changes: {renamed_columns}"
            )
        except Exception as e:
            await self.send_message(message['channel_id'], f"Error: {str(e)}")
            duck_logger.error(f"Error migrating table '{table_name}': {str(e)}")


def create_commands(send_message, metrics_handler, reporter) -> list[Command]:
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
        LogCommand(send_message, BashExecuteCommand(send_message)),
        ActiveWorkflowsCommand(send_message, get_workflow_metrics),
        MigrateTableCommand(send_message, metrics_handler)
    ]
