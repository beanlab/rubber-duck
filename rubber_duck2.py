import asyncio
import logging
import re
import subprocess
import traceback
import uuid
from pathlib import Path
from typing import TypedDict

import discord
import openai
from discord import ChannelType
from openai.openai_object import OpenAIObject

from .metrics import MetricsHandler


def parse_blocks(text: str, limit=2000):
    tick = '`'
    block = ""
    current_fence = ""
    for line in text.splitlines():
        if len(block) + len(line) > limit - 3:
            if block:
                if current_fence:
                    block += '```'
                yield block
                block = current_fence

        block += ('\n' + line) if block else line

        if line.strip().startswith(tick * 3):
            if current_fence:
                current_fence = ""
            else:
                current_fence = line

    if block:
        yield block


class Message(TypedDict):
    guild_id: int
    channel_name: str
    channel_id: int
    author_id: int
    author_name: str
    author_mention: str
    content: str


class GPTMessage(TypedDict):
    role: str
    content: str


class RubberDuck:
    def __init__(self, client: discord.Client, metrics_handler: MetricsHandler, config: dict):
        self._discord: discord.Client = client
        self._metrics_handler: MetricsHandler = metrics_handler
        self._config: dict = config
        self._messages: dict[int | str, asyncio.Queue[Message]] = {}
        self._tasks: dict[int | str, asyncio.Task] = {}

        # TODO initialize listening channel tasks

    async def _send_message(self, channel_id: int, message: str, file: str = None):
        for block in parse_blocks(message):
            await self._discord.get_channel(channel_id).send(block)
        if file is not None:
            await self._discord.get_channel(channel_id).send(file=discord.File(file))

    async def commands_channel(self, channel_id: int):
        while True:
            message = await self._messages[channel_id].get()
            await self._handle_command(message)

    async def _handle_command(self, message: Message):
        """
            This function is called whenever the bot sees a message in a control channel
            :param message:
            :return:
            """
        content = message['content']
        channel_id = message['channel_id']
        try:
            if content.startswith('!restart'):
                await self._restart(channel_id)

            elif content.startswith('!branch'):
                m = re.match(r'!branch\s+(\S+)', content)
                if m is None:
                    await self._send_message(channel_id, 'Error. Usage: !branch <branch name>')
                else:
                    await self._switch_branch(channel_id, m.group(1))

            elif content.startswith('!log'):
                await self._log(channel_id)

            elif content.startswith('!metrics'):
                await self._report_metrics(channel_id)

            elif content.startswith('!status'):
                await self._send_message(channel_id, 'I am alive. 🦆')

            elif content.startswith('!help'):
                await self._display_help(channel_id)

            elif content.startswith('!state'):
                await self._state(channel_id)

            elif content.startswith('!'):
                await self._send_message(channel_id, 'Unknown command. Try !help')

        except:
            logging.exception('Error')
            await self._send_message(channel_id, traceback.format_exc())

    async def _run(self, command):
        work_dir = Path(__file__).parent
        process = subprocess.run(
            command,
            shell=isinstance(command, str), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir
        )
        return process.stdout.decode('utf-8'), process.stderr.decode('utf-8')

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
            "!state - get a zip of the state folder\n"
            "!restart - restart the bot\n"
            "```\n"
        )

    async def _log(self, channel_id):
        await self._execute_command(channel_id, f'zip -q -r log.zip {self._log_file_path}')
        await self._send_message(channel_id, 'log zip', file='log.zip')

    async def _report_metrics(self, channel_id):
        await self._execute_command(channel_id, f'zip -q -r messages.zip {self._metrics_handler._messages_file}')
        await self._send_message(channel_id, 'messages zip', file='messages.zip')

        await self._execute_command(channel_id, f'zip -q -r usage.zip {self._metrics_handler._usage_file}')
        await self._send_message(channel_id, 'usage zip', file='usage.zip')

    async def _restart(self, channel_id):
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
        subprocess.Popen(["bash", "restart.sh"])
        return

    async def _state(self, channel_id):
        await self._send_message(channel_id, "Getting state zip")
        await self._execute_command(channel_id, 'zip -q -r state.zip state')
        await self._send_message(channel_id, 'state zip', file='state.zip')

    async def _switch_branch(self, channel_id, branch_name: str):
        await self._execute_command(channel_id, ['git', 'fetch'])
        await self._execute_command(channel_id, ['git', 'switch', branch_name])

    async def _create_thread(self, parent_channel_id: int, title: str) -> int:
        thread = await self._discord.get_channel(parent_channel_id).create_thread(
            name=title,
            type=ChannelType.public_thread,
            auto_archive_duration=60
        )
        return thread.id

    def _get_prompt(self, channel: str | int) -> str | None:
        config = self._config.get(channel, {})

        prompt = config.get('prompt', None)
        if prompt is not None:
            return prompt

        prompt_file = config.get('prompt_file', None)
        if prompt_file is not None:
            return Path(prompt_file).read_text()

        return None

    def _get_engine(self, channel: str | int) -> str:
        return self._config.get(channel, None) or self._config.get('default_engine')

    async def listen_channel(self, channel_name: str):
        while True:
            message: Message = await self._messages[channel_name].get()
            thread_id = await self._create_thread(
                message['channel_id'],
                message['content'][:20]
            )

            prompt = self._get_prompt(channel_name) or message['content']
            engine = self._get_engine(channel_name)

            self._messages[thread_id] = (queue := asyncio.Queue())
            await queue.put(message)
            self._tasks[thread_id] = asyncio.create_task(self.have_conversation(thread_id, engine, prompt))

    async def _get_completion(self, thread_id, engine, message_history) -> tuple[list, dict]:
        async with self._discord.get_channel(thread_id).typing():
            completion: OpenAIObject = await openai.ChatCompletion.acreate(
                model=engine,
                messages=message_history
            )
            return completion.choices, completion.usage

    async def have_conversation(self, thread_id: int, engine: str, prompt: str):
        message_history = []  # TODO - make this persistent
        while True:
            message: Message = await self._messages[thread_id].get()
            message_history.append(GPTMessage(role='user', content=message['content']))

            user_id = message['author_id']
            guild_id = message['guild_id']

            await self._metrics_handler.record_message(
                guild_id, thread_id, user_id,
                message_history[-1]['role'],
                message_history[-1]['content']
            )

            try:
                choices, usage = await self._get_completion(thread_id, engine, message_history)

                await self._metrics_handler.record_usage(guild_id, thread_id, user_id,
                                                         usage['prompt_tokens'],
                                                         usage['completion_tokens'])

                response_message = choices[0]['message']
                await self._metrics_handler.record_message(
                    guild_id, thread_id, user_id,
                    response_message['role'],
                    response_message['content']
                )

                response = response_message['content'].strip()
                message_history.append(GPTMessage(role='assistant', content=response))

                await self._send_message(thread_id, response)

            except Exception:
                error_code = str(uuid.uuid4()).split('-')[0].upper()
                logging.exception('Error getting completion: ' + error_code)
                await self._send_message(thread_id, f'😵 **Error code {error_code}** 😵'
                                                    f'\nAn error occurred. Please tell a TA or the instructor.')
