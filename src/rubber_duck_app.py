from src.config_types import Config
from src.discord_bot import DiscordBot


class RubberDuckApp:
    def __init__(self, config:Config):
        self.config = config
        self.bot = DiscordBot(config)
