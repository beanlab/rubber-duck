import json

import discord

from src.armory.tools import register_tool


class DiscordTool:
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @register_tool
    async def understand_structure(self, guild_id: int) -> str:
        """
        Reads a Discord server's structure and generates a human-readable explanation.
        Shows categories and which channels belong to each category.
        :param guild_id: int: The ID of the guild to read.
        :return: str: A descriptive string explaining the server's structure.
        """
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise ValueError(f"Guild with id {guild_id} not found or bot is not in that guild.")

        description_lines = [f"Server **{guild.name}** (ID: {guild.id}) structure:"]

        # Group channels by category
        categories = {cat.id: cat for cat in guild.categories}
        category_channels = {cat.id: [] for cat in guild.categories}
        uncategorized = []

        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                if channel.category_id:
                    category_channels[channel.category_id].append(channel)
                else:
                    uncategorized.append(channel)

        for cat_id, cat in categories.items():
            description_lines.append(f"\n📂 Category: {cat.name}")
            if category_channels[cat_id]:
                for ch in category_channels[cat_id]:
                    description_lines.append(f"   - #{ch.name} (ID: {ch.id})")
            else:
                description_lines.append("   _(no channels)_")

        if uncategorized:
            description_lines.append("\n📂 Uncategorized Channels:")
            for ch in uncategorized:
                description_lines.append(f"   - #{ch.name} (ID: {ch.id})")

        return "\n".join(description_lines)

    @register_tool
    async def get_server_structure(self, guild_id: int) -> str:
        """
        Reads a Discord server from its guild_id and returns its structure as a JSON string
        """
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise ValueError(f"Guild with id {guild_id} not found or bot is not in that guild.")

        data = {
            str(guild.id): {
                "server_name": guild.name,
                "channels": [
                    {
                        "channel_id": str(channel.id),
                        "channel_name": channel.name,
                        "ducks": [],
                        "timeout": 600
                    }
                    for channel in guild.channels
                    if isinstance(channel, discord.TextChannel) and channel.name.lower() != "general"
                ]
            }
        }

        return json.dumps(data, indent=2)

    @register_tool
    async def create_category(self, guild_id: int, category_name: str) -> str:
        """Create a category in the given guild. Returns a descriptive string."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return f"Guild with ID {guild_id} not found."

        try:
            category = await guild.create_category(category_name)
            return f"Created category '{category.name}' with ID {category.id} in guild '{guild.name}'."
        except Exception as e:
            return f"Failed to create category '{category_name}' in guild '{guild.name}': {str(e)}"

    @register_tool
    async def create_text_channel(self, guild_id: int, channel_name: str, category_name: str = None) -> str:
        """Create a text channel, optionally inside a category. Returns a descriptive string."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return f"Guild with ID {guild_id} not found."

        category = None
        if category_name:
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(category_name)

        try:
            channel = await guild.create_text_channel(channel_name, category=category)
            if category:
                return f"Created text channel '{channel.name}' (ID: {channel.id}) in category '{category.name}' (ID: {category.id}) in guild '{guild.name}'."
            else:
                return f"Created text channel '{channel.name}' (ID: {channel.id}) in guild '{guild.name}' without a category."
        except Exception as e:
            return f"Failed to create text channel '{channel_name}' in guild '{guild.name}': {str(e)}"

    @register_tool
    async def delete_text_channel(self, guild_id: int, channel_name: str) -> str:
        """Delete a text channel by name. Returns a descriptive string."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return f"Guild with ID {guild_id} not found."

        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if not channel:
            return f"Channel '{channel_name}' not found in guild '{guild.name}'."

        try:
            channel_id = channel.id
            await channel.delete()
            return f"Deleted text channel '{channel_name}' (ID: {channel_id}) from guild '{guild.name}'."
        except Exception as e:
            return f"Failed to delete channel '{channel_name}' in guild '{guild.name}': {str(e)}"

    @register_tool
    async def move_channel_to_category(self, guild_id: int, channel_name: str, category_name: str) -> str:
        """Move a text channel into a category. Returns a descriptive string."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return f"Guild with ID {guild_id} not found."

        channel = discord.utils.get(guild.text_channels, name=channel_name)
        category = discord.utils.get(guild.categories, name=category_name)

        if not channel:
            return f"Channel '{channel_name}' not found in guild '{guild.name}'."
        if not category:
            return f"Category '{category_name}' not found in guild '{guild.name}'."

        try:
            await channel.edit(category=category)
            return f"Moved channel '{channel.name}' (ID: {channel.id}) into category '{category.name}' (ID: {category.id}) in guild '{guild.name}'."
        except Exception as e:
            return f"Failed to move channel '{channel_name}' in guild '{guild.name}': {str(e)}"
