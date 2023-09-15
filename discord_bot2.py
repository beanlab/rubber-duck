import argparse
import json
import logging
import os
from pathlib import Path

import discord
from discord import ChannelType

from rubber_duck import Message, RubberDuck, MessageHandler

LOG_FILE = Path('/tmp/duck.log')


def load_env():
    with open('secrets.env') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            key, value = line.split('=')
            os.environ[key] = value


load_env()


def as_message(message: discord.Message) -> Message:
    return Message(
        channel_name=message.channel.name,
        channel_id=message.channel.id,
        author_id=message.author.id,
        author_name=message.author.name,
        author_mention=message.author.mention,
        content=message.content
    )


class MyClient(discord.Client, MessageHandler):
    def __init__(self, root_save_folder: Path, configs: list[dict]):
        # adding intents module to prevent intents error in __init__ method in newer versions of Discord.py
        intents = discord.Intents.default()  # Select all the intents in your bot settings
        intents.message_content = True
        super().__init__(intents=intents)

        self._rubber_duck = RubberDuck(self, root_save_folder, LOG_FILE, configs)

    async def on_ready(self):
        # print out information when the bot wakes up
        logging.info('Logged in as')
        logging.info(self.user.name)
        logging.info(self.user.id)

        await self._rubber_duck.on_ready()

        logging.info('------')

    async def close(self):
        await self._rubber_duck.close()
        await super().close()

    async def on_message(self, message: discord.Message):
        # ignore messages from the bot itself
        if message.author.id == self.user.id:
            return

        message_info: Message = as_message(message)

        await self._rubber_duck.on_message(message_info)

    #
    # Methods for MessageHandler protocol
    #

    async def create_thread(self, parent_channel_id: int, title: str) -> int:
        thread = await self.get_channel(parent_channel_id).create_thread(
            name=title,
            type=ChannelType.public_thread,
            auto_archive_duration=60
        )
        return thread.id

    async def send_message(self, channel_id, message: str, file=None):
        if file is not None:
            file = discord.File(file)
        await self.get_channel(channel_id).send(message, file=file)

    def typing(self, channel_id):
        return self.get_channel(channel_id).typing()


def main(state_path: Path, configs: list[dict]):
    client = MyClient(state_path, configs)
    client.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-folder', type=Path, default='configs')
    parser.add_argument('--state', type=Path, default='state')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG,
        filename=LOG_FILE,
        format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(message)s'
    )

    configs = [json.loads(config.read_text()) for config in args.config_folder.iterdir()]

    main(args.state, configs)
