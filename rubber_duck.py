import asyncio
import logging
import os
import re
import subprocess
import traceback
import uuid
from pathlib import Path
from typing import TypedDict, Protocol, ContextManager

import openai
from discord import User
from openai.openai_object import OpenAIObject
from quest import create_filesystem_historian, task, step, queue, version

from metrics import MetricsHandler

openai.api_key = os.environ['OPENAI_API_KEY']

AI_ENGINE = 'gpt-4'
CONVERSATION_TIMEOUT = 60 * 3  # three minutes

V_SUPPORT_STATE_COMMAND = '2023-09-26 Support State'
V_LOG_ZIP_STATS = '2023-09-26 Zip log file, Stats'


class Message(TypedDict):
    guild_id: int
    channel_name: str
    channel_id: int
    author_id: int
    author_name: str
    author_mention: str
    message_id: int
    content: str


class GPTMessage(TypedDict):
    role: str
    content: str


class ChannelConfig(TypedDict):
    name: str | None
    id: int | None
    prompt: str | None
    prompt_file: str | None
    engine: str | None
    timeout: int | None


class RubberDuckConfig(TypedDict):
    command_channels: list[int]
    defaults: ChannelConfig
    channels: list[ChannelConfig]


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


class MessageHandler(Protocol):
    async def send_message(self, channel_id: int, message: str, file=None): ...

    async def create_thread(self, parent_id: int, title: str, author_id: int, message_id: int): ...

    def typing(self, channel_id: int) -> ContextManager: ...


def wrap_steps(obj):
    for field in dir(obj):
        if field.startswith('_'):
            continue

        if callable(method := getattr(obj, field)):
            method = step(method)
            setattr(obj, field, method)

    return obj


class RubberDuck:
    def __init__(self,
                 message_handler: MessageHandler,
                 metrics_handler: MetricsHandler,
                 root_state_folder: Path,
                 log_file_path: Path,
                 configs: list[dict]
                 ):
        self._send_raw_message = message_handler.send_message
        self._send_block = step(message_handler.send_message)
        self._create_thread = step(message_handler.create_thread)
        self._typing = message_handler.typing

        self._metrics_handler = wrap_steps(metrics_handler)

        self._log_file_path = log_file_path
        self._configs = configs
        self._command_channels = configs[-1]['command_channels']
        self._command_channel_tasks: dict[int, asyncio.Task] = {}
        self._channel_tasks: dict[str, asyncio.Task] = {}

        if not root_state_folder.exists():
            root_state_folder.mkdir(parents=True)

        self._conversation_manager = create_filesystem_historian(
            root_state_folder,
            'conversation_manager',
            self.conversation_manager
        )
        self._conversation_manager_task = None  # started in on_ready

    async def on_ready(self):
        for config in self._configs:
            self._conversation_manager.configure(self.configure, config)

        self._conversation_manager_task = self._conversation_manager.run()

        await asyncio.sleep(0.1)  # allow the conversation manager to warm up
        await self._conversation_manager.get_resources(None)  # check that it's up

        logging.info('Rubber Duck ready 🦆')

        for channel_id in self._command_channels:
            try:
                await self._send_raw_message(channel_id, 'Duck online')
            except:
                logging.exception(f'Unable to message channel {channel_id}')

        logging.info('------')

    async def close(self):
        for channel_id in self._command_channels:
            try:
                await self._send_raw_message(channel_id, 'Duck online')
            except:
                logging.exception(f'Unable to message channel {channel_id}')
        await self._conversation_manager.suspend()

    async def on_message(self, message: Message):
        # ignore messages that start with //
        if message['content'].startswith('//'):
            return

        # First check if the channel ID is registered
        identity = str(message['channel_id'])
        resources = await self._conversation_manager.get_resources(identity)

        if 'messages' not in resources:
            # See if the channel name is registered
            identity = str(message['channel_name'])
            resources = await self._conversation_manager.get_resources(identity)

        if 'messages' not in resources:
            # Neither the channel ID nor channel name are watched, so ignore this message
            return

        await self._conversation_manager.record_external_event('messages', identity, 'put', message)

    #
    # Begin Conversation Management
    #

    async def conversation_manager(self):
        await asyncio.Future()  # i.e. run forever

    async def configure(self, config: RubberDuckConfig):
        # Add new command channels
        for channel_id in config['command_channels']:
            if channel_id not in self._command_channel_tasks:
                self._command_channel_tasks[channel_id] = self.command_channel(channel_id)

        # Remove old command channels
        for channel_id, channel_task in self._command_channel_tasks.items():
            if channel_id not in config['command_channels']:
                channel_task.cancel()
                try:
                    await channel_task
                except asyncio.CancelledError:
                    pass

        # Add new listen channels
        for channel_config in config['channels']:
            if channel_config['name'] not in self._channel_tasks:
                self._channel_tasks[channel_config['name']] = \
                    self.listen_channel(config['defaults'], channel_config)

        # Remove old listen channels
        valid_channels = set(c['name'] for c in config['channels'])
        for channel_name, channel_task in self._channel_tasks.items():
            if channel_name not in valid_channels:
                channel_task.cancel()
                try:
                    await channel_task
                except asyncio.CancelledError:
                    pass

    @task
    @step
    async def command_channel(self, channel_id: int):
        async with queue('messages', str(channel_id)) as messages:
            while True:
                message: Message = await messages.get()
                await self._handle_command(message)

    @task
    @step
    async def listen_channel(self, defaults: ChannelConfig, config: ChannelConfig):
        async with queue('messages', config['name']) as messages:
            while True:
                message: Message = await messages.get()
                thread_id = await self._create_thread(
                    message['channel_id'],
                    message['content'][:20],
                    message['author_id'],
                    message['message_id']
                )
                prompt = config.get('prompt', None)
                if prompt is None:
                    prompt_file = config.get('prompt_file', None)
                    if prompt_file is None:
                        prompt = message['content']
                    else:
                        prompt = Path(prompt_file).read_text()

                engine = config.get('engine', defaults['engine'])

                timeout = config.get('timeout', defaults['timeout'])

                self.have_conversation(thread_id, engine, prompt, message, timeout)

    @step
    async def _send_message(self, channel_id, message: str, file=None):
        for block in parse_blocks(message):
            await self._send_block(channel_id, block)
        if file is not None:
            await self._send_block(channel_id, "", file=file)

    #
    # Begin Conversation
    #
    @task
    @step
    @version(V_LOG_ZIP_STATS)
    async def have_conversation(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
        async with queue('messages', str(thread_id)) as messages:
            message_history = [
                GPTMessage(role='system', content=prompt)
            ]
            user_id = initial_message['author_id']
            guild_id = initial_message['guild_id']
            await self._metrics_handler.record_message(
                guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])

            await self._send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

            while True:
                # TODO - if the conversation is getting long, and the user changes the subject
                #  prompt them to start a new conversation (and close this one)
                try:
                    message: Message = await asyncio.wait_for(messages.get(), timeout)

                except asyncio.TimeoutError:
                    await self._send_message(thread_id, '*This conversation has been closed.*')
                    return

                message_history.append(GPTMessage(role='user', content=message['content']))

                user_id = message['author_id']
                guild_id = message['guild_id']

                await self._metrics_handler.record_message(
                    guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content'])

                try:
                    choices, usage = await self._get_completion(thread_id, engine, message_history)
                    response_message = choices[0]['message']
                    response = response_message['content'].strip()

                    await self._metrics_handler.record_usage(guild_id, thread_id, user_id,
                                                             usage['prompt_tokens'],
                                                             usage['completion_tokens'])

                    await self._metrics_handler.record_message(
                        guild_id, thread_id, user_id, response_message['role'], response_message['content'])

                    message_history.append(GPTMessage(role='assistant', content=response))

                    await self._send_message(thread_id, response)

                except Exception:
                    error_code = str(uuid.uuid4()).split('-')[0].upper()
                    logging.exception('Error getting completion: ' + error_code)
                    # TODO - send the control channel the thread link, error code, and full error message\
                    # For now, we need to look up the error in the logs.
                    await self._send_message(thread_id, f'😵 **Error code {error_code}** 😵'
                                                        f'\nAn error occurred.'
                                                        f'\nPlease tell a TA or the instructor the error code.'
                                                        '\n*This conversation is closed*')
                    return

    @step
    async def _get_completion(self, thread_id, engine, message_history) -> tuple[list, dict]:
        # Replaces _get_response
        async with self._typing(thread_id):
            completion: OpenAIObject = await openai.ChatCompletion.acreate(
                model=engine,
                messages=message_history
            )
            logging.debug(f"Completion: {completion}")
            return completion.choices, completion.usage

    @step
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
            "!state - get a zip of the state folder\n"
            "!restart - restart the bot\n"
            "```\n"
        )

    @step
    async def _log(self, channel_id):
        await self._execute_command(channel_id, f'zip -q -r log.zip {self._log_file_path}')
        await self._send_message(channel_id, 'log zip', file='log.zip')

    @step
    async def _report_metrics(self, channel_id):
        await self._execute_command(channel_id, f'zip -q -r messages.zip {self._metrics_handler._messages_file}')
        await self._send_message(channel_id, 'messages zip', file='messages.zip')

        await self._execute_command(channel_id, f'zip -q -r usage.zip {self._metrics_handler._usage_file}')
        await self._send_message(channel_id, 'usage zip', file='usage.zip')

    @step
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

    @step
    async def _state(self, channel_id):
        await self._send_message(channel_id, "Getting state zip")
        await self._execute_command(channel_id, 'zip -q -r state.zip state')
        await self._send_message(channel_id, 'state zip', file='state.zip')

    async def _switch_branch(self, channel_id, branch_name: str):
        await self._execute_command(channel_id, ['git', 'fetch'])
        await self._execute_command(channel_id, ['git', 'switch', branch_name])
