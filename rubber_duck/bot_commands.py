import datetime
import logging
import re
import subprocess
import traceback
from pathlib import Path

import discord
from quest import step

import reporter
from rubber_duck import Message


class BotCommands:
    def __init__(self, send_message, metrics_handler, reporter):
        self._send_message = step(send_message)
        self._metrics_handler = metrics_handler
        self._reporter = reporter

    async def __call__(self, message: Message):
        return await self.handle_command(message)

    async def handle_command(self, message: Message):
        """
            This function is called whenever the bot sees a message in a control channel
            :param message:
            :return:
            """
        content = message['content']
        channel_id = message['channel_id']
        try:
            if content.startswith('!restart'):
                await self._send_message(channel_id, 'The restart command has been temporarily disabled.')
                # await self._restart(channel_id)

            elif content.startswith('!clean-restart'):
                await self._send_message(channel_id, 'The clean-restart command has been temporarily disabled.')
                # await self._restart(channel_id, clean=True)

            elif content.startswith('!branch'):
                m = re.match(r'!branch\s+(\S+)', content)
                if m is None:
                    await self._send_message(channel_id, 'Error. Usage: !branch <branch name>')
                else:
                    await self._switch_branch(channel_id, m.group(1))

            elif content.startswith('!log'):
                await self._log(channel_id)

            elif content.startswith('!metrics'):
                await self._zip_metrics(channel_id)

            elif content.startswith('!status'):
                await self._send_message(channel_id, 'I am alive. 🦆')

            elif content.startswith('!help'):
                await self._display_help(channel_id)

            elif content.startswith('!report'):
                await self._send_report(channel_id, content)

            elif content.startswith('!state'):
                await self._state(channel_id)

            elif content.startswith('!'):
                await self._send_message(channel_id, 'Unknown command. Try !help')

        except:
            logging.exception('Error')
            await self._send_message(channel_id, traceback.format_exc())

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

    async def _display_help(self, channel_id):
        await self._send_message(
            channel_id,
            "```\n"
            "!status - print a status message\n"
            "!help - print this message\n"
            "!log - get the log file\n"
            "!metrics - get the zips of the data tables\n"
            "!state - get a zip of the state folder\n"
            "!restart - restart the bot\n"
            "!clean-restart - wipe the state and restart the bot\n"
            "```\n"
        )

    @step
    async def _log(self, channel_id):
        await self._execute_command(channel_id, f'zip -q -r log.zip {self._log_file_path}')
        await self._send_message(channel_id, 'log zip', file='log.zip')

    @step
    async def _send_report(self, channel_id, arg_string):
        img_name, img = self._reporter.get_report(arg_string)
        if img is None:
            await self._send_message(channel_id, img_name)

        elif isinstance(img, list):
            imgs = [discord.File(fp=image, filename=image_name) for image, image_name in zip(img, img_name)]
            await self._send_message(channel_id, img_name, files=imgs)

        else:
            await self._send_message(channel_id, img_name, file=discord.File(fp=img, filename=img_name))

    @step
    async def _zip_metrics(self, channel_id):
        messages_zip = reporter.zip_data_file(self._metrics_handler.get_messages())
        usage_zip = reporter.zip_data_file(self._metrics_handler.get_usage())
        feedback_zip = reporter.zip_data_file(self._metrics_handler.get_feedback())

        discord_messages_file = discord.File(messages_zip, filename="messages.zip")
        discord_usage_file = discord.File(usage_zip, filename="usage.zip")
        discord_feedback_file = discord.File(feedback_zip, filename="feedback.zip")

        await self._send_message(channel_id, "", file=discord_messages_file)
        await self._send_message(channel_id, "", file=discord_usage_file)
        await self._send_message(channel_id, "", file=discord_feedback_file)

    @step
    async def _restart(self, channel_id, clean=False):
        """
        Restart the bot
        """
        await self._send_message(channel_id, f'Restart requested.')
        await self._execute_command(channel_id, 'git fetch')
        await self._execute_command(channel_id, 'git reset --hard')
        await self._execute_command(channel_id, 'git clean -f')
        await self._execute_command(channel_id, 'git pull --rebase=false')
        await self._execute_command(channel_id, 'rm poetry.lock')
        await self._execute_command(channel_id, 'poetry install')
        await self._send_message(channel_id, f'Restarting.')

        if clean:
            timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")
            await self._send_message(channel_id, f'mv state state-{timestamp}.')

            # Don't run this as a step, as we are essentially deleting the state folder
            subprocess.check_output(f'mv state state-{timestamp}')

        # This script will kill and restart the python process
        subprocess.Popen(["bash", "restart.sh"])
        return

    @step
    async def _state(self, channel_id):
        await self._send_message(channel_id, "Getting state zip")
        await self._execute_command(channel_id, 'zip -q -r state.zip state')
        await self._send_message(channel_id, 'state zip', file='state.zip')

    async def _switch_branch(self, channel_id, branch_name: str):
        await self._execute_command(channel_id, ['git', 'fetch'])
        await self._execute_command(channel_id, ['git', 'switch', branch_name])
