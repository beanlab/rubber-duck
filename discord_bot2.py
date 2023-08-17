import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from discord import ChannelType
from quest import task, step
from quest.external import queue
from quest.historian import Historian
from quest.local_persistence import LocalJsonHistory

logging.basicConfig(level=logging.DEBUG)

# the Discord Python API
import discord
import openai


def load_env():
    with open('secrets.env') as file:
        for line in file:
            key, value = line.strip().split('=')
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
    def __init__(self, root_save_folder: Path, prompt_dir: Path):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)

        self._prompts = self._load_prompts(prompt_dir)

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
        logging.info('------')

        self._conversation_manager_task = asyncio.create_task(self._conversation_manager.run())

    async def on_message(self, message: discord.Message):
        # ignore messages from the bot itself
        if message.author.id == self.user.id:
            return

        message_info: Message = as_message(message)
        await self._conversation_manager.record_external_event('messages', None, 'put', message_info)

    #
    # Begin Conversation Management
    #

    async def conversation_manager(self):
        clean_up_task = self._clean_up()

        async with queue('messages', None) as messages:
            while True:
                next_message: Message = await messages.get()

                if next_message['channel_name'] in self.prompts:
                    # Start new conversation
                    await self._create_conversation(next_message)

                else:
                    # Delegate message
                    await self._delegate_message(next_message)

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

    async def _delegate_message(self, message: Message):
        if (convo := self._conversation_queues.get(message['channel_id'], None)) is not None:
            await convo.put(message)
        else:
            return  # ignore message

    @step
    async def _send_block(self, channel_id, block):
        await self.get_channel(channel_id).send(block)

    @step
    async def send_message(self, channel_id, message: str):
        for block in parse_blocks(message):
            await self._send_block(channel_id, block)

    #
    # Begin Conversation
    #
    @task
    async def have_conversation(self, thread_id, initial_message):
        message_history = []
        message_queue = self._conversation_queues[thread_id]

        await self.send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

        while True:
            message: Message = await message_queue.get()
            message_history.append(GPTMessage(role='user', content=message['content']))

            response = await self.get_response(thread_id, message_history)
            message_history.append(GPTMessage(role='assistant', content=response))
            await self.send_message(thread_id, response)

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


async def display_help(message):
    await message.channel.send(
        "!restart - restart the bot\n"
        "!log - print the log file\n"
        "!rmlog - remove the log file\n"
        "!status - print a status message\n"
        "!help - print this message\n"
    )


async def execute_command(text, channel):
    """
    Execute a command in the shell and return the output to the channel
    """
    # Run command using shell and pipe output to channel
    work_dir = Path(__file__).parent
    await send(channel, f"```ps\n$ {text}```")
    process = subprocess.run(text, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work_dir)
    # Get output of command and send to channel
    errors = process.stderr.decode('utf-8')
    if errors:
        await send(channel, f'Errors: ```{errors}```')
    output = process.stdout.decode('utf-8')
    if output:
        await send(channel, f'```{output}```')
    return


async def restart(message):
    """
    Restart the bot
    :param message: The message that triggered the restart
    """
    await message.channel.send(f'Restart requested.')
    await execute_command('git fetch', message.channel)
    await execute_command('git reset --hard', message.channel)
    await execute_command('git clean -f', message.channel)
    await execute_command('git pull --rebase=false', message.channel)
    await execute_command('rm poetry.lock', message.channel)
    await execute_command('poetry install', message.channel)
    await message.channel.send(f'Restarting.')
    subprocess.Popen(["bash", "restart.sh"])
    return


async def control_on_message(message):
    """
    This function is called whenever the bot sees a message in a control channel
    :param message:
    :return:
    """
    content = message.content
    if content.startswith('!restart'):
        await restart(message)

    elif content.startswith('!log'):
        await message.channel.send(file=discord.File('/tmp/duck.log'))

    elif content.startswith('!rmlog'):
        await execute_command("rm /tmp/duck.log", message.channel)
        await execute_command("touch /tmp/duck.log", message.channel)

    elif content.startswith('!status'):
        await message.channel.send('I am alive.')

    elif content.startswith('!help'):
        await display_help(message)
    elif content.startswith('!'):
        await message.channel.send('Unknown command. Try !help')


class MyClient(discord.Client):
    def __init__(self, prompt_dir: Path, conversation_dir: Path):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings as it's easier
        intents.message_content = True
        super().__init__(intents=intents)

        self._load_prompts(prompt_dir)
        self._load_control_channels()
        self.conversation_dir = conversation_dir
        self.conversations = {}
        self.guild_dict = {}  # Loaded in on_ready

    def _load_prompts(self, prompt_dir: Path):
        self.prompts = {}
        for file in prompt_dir.iterdir():
            if file.suffix == '.txt':
                self.prompts[file.stem] = file.read_text()

    def __enter__(self):
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        # serialize the conversations
        logging.info('Serializing conversations')
        for conversation in self.conversations.values():
            self._serialize_conversation(conversation)
        logging.info('Done serializing conversations')

    def _handle_interrupt(self, signum=None, frame=None):
        self.__exit__()
        exit()

    def _serialize_conversation(self, conversation: Conversation):
        # Save conversation as JSON in self.conversations_dir
        logging.debug(f'Serializing conversation {conversation.thread_id}')
        filename = f'{conversation.guild_id}_{conversation.thread_id}.json'
        with open(self.conversation_dir / filename, 'w') as file:
            json.dump(conversation.to_json(), file)

    def _load_conversation(self, filename: str):
        # Load conversation from JSON in self.conversations_dir
        logging.debug(f'Loading conversation {filename}')
        try:
            with open(self.conversation_dir / filename) as file:
                jobj = json.load(file)

            guild = self.guild_dict.get(jobj['guild_id'])
            if guild is None:
                return
            thread_id = jobj['thread_id']
            thread = self.get_channel(thread_id)
            self.conversations[thread_id] = Conversation.from_json(jobj, thread)
        except Exception as ex:
            logging.exception(f"Unable to load conversation: {filename}")

    async def on_ready(self):
        self.guild_dict = {guild.id: guild async for guild in self.fetch_guilds(limit=150)}

        # Load conversations from JSON in self.conversations_dir
        logging.info('Loading conversations')
        for file in self.conversation_dir.iterdir():
            if file.suffix == '.json':
                self._load_conversation(file.name)
        logging.info('Done loading conversations')

        # print out information when the bot wakes up
        logging.info('Logged in as')
        logging.info(self.user.name)
        logging.info(self.user.id)
        logging.info('------')
        for channel in self.control_channels:
            await channel.send('Duck online')

    async def on_message(self, message: discord.Message):
        """
        This function is called whenever the bot sees a message in a channel
        If the message is in a listen channel
          the bot creates a thread in response to that message
        If the message is in a conversation thread,
          the bot continues the conversation in that thread
        The bot ignores all other messages.
        """
        # ignore messages from the bot itself
        if message.author == self.user:
            return

        if message.content.startswith('//'):
            return

        if message.channel.id in self.control_channel_ids:
            await control_on_message(message)
            return

        # if the message is in a listen channel, create a thread
        if message.channel.name in self.prompts:
            await self.create_conversation(self.prompts[message.channel.name], message)

        # if the message is in an active thread, continue the conversation
        elif message.channel.id in self.conversations:
            await continue_conversation(
                self.conversations[message.channel.id], message.content)

        # otherwise, ignore the message
        else:
            return

    async def create_conversation(self, prefix, message):
        """
        Create a thread in response to this message.
        """
        # get the channel from the message
        channel = message.channel

        # create a public thread in response to the message
        thread = await channel.create_thread(
            name=message.content[:20],
            type=ChannelType.public_thread,
            auto_archive_duration=60
        )
        welcome = f'{message.author.mention} What can I do for you?'

        conversation = Conversation(
            guild_id=thread.guild.id,
            thread=thread,
            thread_id=thread.id,
            thread_name=thread.name,
            started_by=message.author.name,
            first_message=datetime.utcnow(),
            last_message=datetime.utcnow(),
            messages=[
                dict(role='system', content=prefix or message.content),
                dict(role='assistant', content=welcome)
            ]
        )
        self.conversations[thread.id] = conversation
        async with thread.typing():
            await thread.send(welcome)

    def _load_control_channels(self):
        with open('config.json') as file:
            config = json.load(file)
        self.control_channel_ids = config['control_channels']
        self.control_channels = [c for c in self.get_all_channels() if c.id in self.control_channel_ids]


def main(prompts: Path, conversations: Path):
    with MyClient(prompts, conversations) as client:
        client.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prompts', type=Path, default='prompts')
    parser.add_argument('--conversations', type=Path, default='conversations')
    args = parser.parse_args()
    main(args.prompts, args.conversations)
