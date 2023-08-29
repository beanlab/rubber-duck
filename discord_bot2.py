import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import traceback
import uuid
from pathlib import Path
from typing import TypedDict

from discord import ChannelType
from quest import task, step, queue, create_filesystem_historian, state

LOG_FILE = '/tmp/duck.log'

# the Discord Python API
import discord
import openai


def load_env():
    with open('secrets.env') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            key, value = line.split('=')
            os.environ[key] = value


load_env()
openai.api_key = os.environ['OPENAI_API_KEY']

AI_ENGINE = 'gpt-4'
CONVERSATION_TIMEOUT = 60 * 3  # three minutes


class ChannelConfig(TypedDict):
    name: str
    prompt: str | None
    prompt_file: str | None
    engine: str | None


class RubberDuckConfig(TypedDict):
    command_channels: list[int]
    default_engine: str
    channels: list[ChannelConfig]


class GPTMessage(TypedDict):
    role: str
    content: str


class Message(TypedDict):
    channel_name: str
    channel_id: int
    author_id: int
    author_name: str
    author_mention: str
    content: str


def as_message(message: discord.Message) -> Message:
    return Message(
        channel_name=message.channel.name,
        channel_id=message.channel.id,
        author_id=message.author.id,
        author_name=message.author.name,
        author_mention=message.author.mention,
        content=message.content
    )


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


class MyClient(discord.Client):
    def __init__(self, root_save_folder: Path, config: dict):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings
        intents.message_content = True
        super().__init__(intents=intents)

        self._config = config
        self._command_channels = config['command_channels']

        self._root_folder = root_save_folder
        self._conversation_manager = create_filesystem_historian(
            root_save_folder,
            'conversation_manager',
            self.conversation_manager
        )
        self._conversation_manager_task = None  # started in on_ready

    async def on_ready(self):
        # print out information when the bot wakes up
        logging.info('Logged in as')
        logging.info(self.user.name)
        logging.info(self.user.id)

        self._conversation_manager_task = self._conversation_manager.run(config)
        await asyncio.sleep(0.1)  # allow the conversation manager to warm up
        logging.info('Ready')
        for channel_id in self._command_channels:
            channel = self.get_channel(channel_id)
            if channel is None:
                logging.error(f'Unable to access channel {channel_id}')
                continue
            await channel.send('Duck online')
        logging.info('------')

    async def close(self):
        for channel_id in self._command_channels:
            channel = self.get_channel(channel_id)
            if channel is None:
                logging.error(f'Unable to access channel {channel_id}')
                continue
            await channel.send('Duck closing')
        await self._conversation_manager.suspend()
        await super().close()

    async def on_message(self, message: discord.Message):
        # ignore messages from the bot itself
        if message.author.id == self.user.id:
            return

        # ignore messages that start with //
        if message.content.startswith('//'):
            return

        message_info: Message = as_message(message)

        # First check if the channel ID is registered
        identity = str(message.channel.id)
        resources = await self._conversation_manager.get_resources(identity)

        if 'messages' not in resources:
            # See if the channel name is registered
            identity = str(message.channel.name)
            resources = await self._conversation_manager.get_resources(identity)

        if 'messages' not in resources:
            # Neither the channel ID nor channel name are watched, so ignore this message
            return

        await self._conversation_manager.record_external_event('messages', identity, 'put', message_info)

    #
    # Begin Conversation Management
    #

    async def conversation_manager(self, config: RubberDuckConfig):
        # TODO - figure out how to handle changes to the config
        # The original configuration is baked in the history and can't change
        # so we need a way to communicate and track updates to the config
        # over time. Add this feature to quest, then use it here.

        for channel_id in config['command_channels']:
            self.command_channel(channel_id)

        for channel_config in config['channels']:
            self.listen_channel(config['default_engine'], channel_config)

        await asyncio.Future()  # i.e. run forever

    @task
    @step
    async def command_channel(self, channel_id: int):
        async with queue('messages', str(channel_id)) as messages:
            while True:
                message: Message = await messages.get()
                await self._handle_command(message)

    @task
    @step
    async def listen_channel(self, default_engine: str, config: ChannelConfig):
        async with queue('messages', config['name']) as messages:
            while True:
                message: Message = await messages.get()
                thread_id = await self._create_thread(
                    message['channel_id'],
                    message['content'][:20]
                )
                prompt = config.get('prompt', None)
                if prompt is None:
                    prompt_file = config.get('prompt_file', None)
                    if prompt_file is None:
                        prompt = message['content']
                    else:
                        prompt = Path(prompt_file).read_text()

                engine = config.get('engine', default_engine)

                self.have_conversation(thread_id, engine, prompt, message)

    @step
    async def _create_thread(self, parent_channel_id: int, title: str) -> int:
        thread = await self.get_channel(parent_channel_id).create_thread(
            name=title,
            type=ChannelType.public_thread,
            auto_archive_duration=60
        )
        return thread.id

    @step
    async def _send_block(self, channel_id, block):
        await self.get_channel(channel_id).send(block)

    @step
    async def _send_message(self, channel_id, message: str, file=None):
        for block in parse_blocks(message):
            await self._send_block(channel_id, block)
        if file is not None:
            await self.get_channel(channel_id).send(file=file)

    #
    # Begin Conversation
    #
    @task
    @step
    async def have_conversation(self, thread_id: int, engine: str, prompt: str, initial_message: Message):
        async with queue('messages', str(thread_id)) as messages:
            message_history = [
                GPTMessage(role='system', content=prompt)
            ]

            await self._send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

            while True:
                message: Message = await messages.get()
                message_history.append(GPTMessage(role='user', content=message['content']))

                try:
                    response = await self._get_response(thread_id, engine, message_history)
                    message_history.append(GPTMessage(role='assistant', content=response))

                    await self._send_message(thread_id, response)

                except Exception:
                    error_code = str(uuid.uuid4()).split('-')[0].upper()
                    logging.exception('Error getting completion: ' + error_code)
                    await self._send_message(thread_id, f'😵 **Error code {error_code}** 😵'
                                                        f'\nAn error occurred. Please tell a TA or the instructor.')

    @step
    async def _get_response(self, thread_id, engine, message_history) -> str:
        async with self.get_channel(thread_id).typing():
            completion = await openai.ChatCompletion.acreate(
                model=engine,
                messages=message_history
            )
            logging.debug(f"Completion: {completion}")

            response_message = completion.choices[0]['message']
            response = response_message['content'].strip()

            return response

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
                await self._send_message(channel_id, 'Log', file=discord.File(LOG_FILE))

            elif content.startswith('!status'):
                await self._send_message(channel_id, 'I am alive. 🦆')

            elif content.startswith('!help'):
                await self._display_help(channel_id)

            elif content.startswith('!'):
                await self._send_message(channel_id, 'Unknown command. Try !help')

        except:
            logging.exception('Error')
            await self._send_message(channel_id, traceback.format_exc())

    async def _execute_command(self, text, channel_id):
        """
        Execute a command in the shell and return the output to the channel
        """
        # Run command using shell and pipe output to channel
        work_dir = Path(__file__).parent
        await self._send_message(channel_id, f"```bash\n$ {text}```")
        process = subprocess.run(
            text,
            shell=isinstance(text, str), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir
        )
        # Get output of command and send to channel
        errors = process.stderr.decode('utf-8')
        if errors:
            await self._send_message(channel_id, f'Errors: ```{errors}```')
        output = process.stdout.decode('utf-8')
        if output:
            await self._send_message(channel_id, f'```{output}```')
        return

    async def _display_help(self, channel_id):
        await self._send_message(
            channel_id,
            "```\n"
            "!status - print a status message\n"
            "!help - print this message\n"
            "!log - print the log file\n"
            "!restart - restart the bot\n"
            "```\n"
        )

    async def _restart(self, channel_id):
        """
        Restart the bot
        :param message: The message that triggered the restart
        """
        await self._send_message(channel_id, f'Restart requested.')
        await self._execute_command('git fetch', channel_id)
        await self._execute_command('git reset --hard', channel_id)
        await self._execute_command('git clean -f', channel_id)
        await self._execute_command('git pull --rebase=false', channel_id)
        await self._execute_command('rm poetry.lock', channel_id)
        await self._execute_command('poetry install', channel_id)
        await self._send_message(channel_id, f'Restarting.')
        subprocess.Popen(["bash", "restart.sh"])
        return

    async def _switch_branch(self, channel_id, branch_name: str):
        await self._execute_command(['git', 'fetch'], channel_id)
        await self._execute_command(['git', 'switch', branch_name], channel_id)


def main(state_path: Path, config: dict):
    client = MyClient(state_path, config)
    client.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default='config.json')
    parser.add_argument('--state', type=Path, default='state')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG,
        filename=LOG_FILE,
        format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
    )

    config = json.loads(args.config.read_text())

    main(args.state, config)
