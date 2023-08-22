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
from quest import task, step
from quest.external import queue
from quest.historian import Historian
from quest.local_persistence import LocalJsonHistory

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

        self._command_channels = config['command_channels']
        self._prompts = {
            entry['name']: entry.get('prompt', Path(entry.get('prompt-file')).read_text())
            for entry in config['channels'].items()
        }
        self._engines = {
            entry['name']: entry.get('engine', config['default-engine'])
            for entry in config['channels'].items()
        }

        self._root_folder = root_save_folder
        self._conversation_manager = Historian(
            'conversation_manager',
            self.conversation_manager,
            LocalJsonHistory(root_save_folder)
        )
        self._conversation_manager_task = None  # started in on_ready
        self._conversation_queues: dict[int, asyncio.Queue] = {}
        self._conversation_tasks: dict[int, asyncio.Task] = {}

    def _load_prompts(self, prompt_dir: Path):
        self.prompts = {}
        for file in prompt_dir.iterdir():
            if file.suffix == '.txt':
                self.prompts[file.stem] = file.read_text()

    async def on_ready(self):
        # print out information when the bot wakes up
        logging.info('Logged in as')
        logging.info(self.user.name)
        logging.info(self.user.id)

        self._conversation_manager_task = asyncio.create_task(self._conversation_manager.run())
        await asyncio.sleep(0.1)
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
        self._conversation_manager.suspend()
        await super().close()

    async def on_message(self, message: discord.Message):
        # ignore messages from the bot itself
        if message.author.id == self.user.id:
            return

        # ignore messages that start with //
        if message.content.startswith('//'):
            return

        message_info: Message = as_message(message)
        await self._conversation_manager.record_external_event('messages', None, 'put', message_info)

    #
    # Begin Conversation Management
    #

    async def conversation_manager(self):
        # clean_up_task = self._clean_up()

        async with queue('messages', None) as messages:
            while True:
                next_message: Message = await messages.get()

                if next_message['channel_id'] in self._command_channels:
                    await self._handle_command(next_message)

                elif next_message['channel_name'] in self.prompts:
                    # Start new conversation
                    await self._create_conversation(next_message)

                elif (convo := self._conversation_queues.get(next_message['channel_id'], None)) is not None:
                    # Delegate to the conversation thread
                    await convo.put(next_message)

                else:
                    return  # ignore message

    @task
    async def _clean_up(self):
        await asyncio.sleep(60)
        for cid, ctask in self._conversation_tasks.items():
            if ctask.done():
                logging.info(f'Closing conversation {cid}')
                result = await ctask
                del self._conversation_tasks[cid]
                del self._conversation_queues[cid]

    @step
    async def _create_thread(self, message: Message) -> int:
        thread = await self.get_channel(message['channel_id']).create_thread(
            name=message['content'][:20],
            type=ChannelType.public_thread,
            auto_archive_duration=60
        )
        return thread.id

    async def _create_conversation(self, message: Message):
        # Create a private thread in the message channel
        thread_id = await self._create_thread(message)
        self._conversation_queues[thread_id] = (message_queue := asyncio.Queue())
        self._conversation_tasks[thread_id] = self.have_conversation(thread_id, message)

    @step
    async def _send_block(self, channel_id, block):
        await self.get_channel(channel_id).send(block)

    @step
    async def send_message(self, channel_id, message: str, file=None):
        for block in parse_blocks(message):
            await self._send_block(channel_id, block)
        if file is not None:
            await self.get_channel(channel_id).send(file=file)

    #
    # Begin Conversation
    #
    @task
    async def have_conversation(self, thread_id: int, initial_message: Message):
        message_history = []

        prompt = self.prompts.get(initial_message['channel_name'], None)
        if prompt is not None:
            message_history.append(GPTMessage(role='system', content=prompt))

        message_queue = self._conversation_queues[thread_id]

        await self.send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

        while True:
            message: Message = await message_queue.get()
            message_history.append(GPTMessage(role='user', content=message['content']))

            try:
                response = await self.get_response(thread_id, message_history)
                message_history.append(GPTMessage(role='assistant', content=response))

                await self.send_message(thread_id, response)

            except Exception:
                error_code = str(uuid.uuid4()).split('-')[0].upper()
                logging.exception('Error getting completion: ' + error_code)
                await self.send_message(thread_id, f'😵 **Error code {error_code}** 😵'
                                                   f'\nAn error occurred. Please tell a TA or the instructor.')

    @step
    async def get_response(self, thread_id, message_history) -> str:
        async with self.get_channel(thread_id).typing():
            completion = await openai.ChatCompletion.acreate(
                model=AI_ENGINE,
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
                await self.restart(channel_id)

            elif content.startswith('!branch'):
                m = re.match(r'!branch\s+(\S+)', content)
                if m is None:
                    await self.send_message(channel_id, 'Error. Usage: !branch <branch name>')
                else:
                    await self.switch_branch(channel_id, m.group(1))

            elif content.startswith('!log'):
                await self.send_message(channel_id, 'Log', file=discord.File(LOG_FILE))

            elif content.startswith('!status'):
                await self.send_message(channel_id, 'I am alive. 🦆')

            elif content.startswith('!help'):
                await self.display_help(channel_id)

            elif content.startswith('!'):
                await self.send_message(channel_id, 'Unknown command. Try !help')

        except:
            logging.exception('Error')
            await self.send_message(channel_id, traceback.format_exc())

    async def _execute_command(self, text, channel_id):
        """
        Execute a command in the shell and return the output to the channel
        """
        # Run command using shell and pipe output to channel
        work_dir = Path(__file__).parent
        await self.send_message(channel_id, f"```bash\n$ {text}```")
        process = subprocess.run(
            text,
            shell=isinstance(text, str), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir
        )
        # Get output of command and send to channel
        errors = process.stderr.decode('utf-8')
        if errors:
            await self.send_message(channel_id, f'Errors: ```{errors}```')
        output = process.stdout.decode('utf-8')
        if output:
            await self.send_message(channel_id, f'```{output}```')
        return

    async def display_help(self, channel_id):
        await self.send_message(
            channel_id,
            "!restart - restart the bot\n"
            "!log - print the log file\n"
            "!status - print a status message\n"
            "!help - print this message\n"
        )

    async def restart(self, channel_id):
        """
        Restart the bot
        :param message: The message that triggered the restart
        """
        await self.send_message(channel_id, f'Restart requested.')
        await self._execute_command('git fetch', channel_id)
        await self._execute_command('git reset --hard', channel_id)
        await self._execute_command('git clean -f', channel_id)
        await self._execute_command('git pull --rebase=false', channel_id)
        await self._execute_command('rm poetry.lock', channel_id)
        await self._execute_command('poetry install', channel_id)
        await self.send_message(channel_id, f'Restarting.')
        subprocess.Popen(["bash", "restart.sh"])
        return

    async def switch_branch(self, channel_id, branch_name: str):
        await self._execute_command(['git', 'fetch'], channel_id)
        await self._execute_command(['git', 'switch', branch_name], channel_id)


def main(state_path: Path, config: dict):
    client = MyClient(state_path, config)
    client.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename=LOG_FILE,
        format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
    )
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default='config.json')
    parser.add_argument('--state', type=Path, default='state')
    args = parser.parse_args()

    config = json.loads(args.config.read_text())

    main(args.state, config)
