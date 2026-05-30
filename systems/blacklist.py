# cattito - A Discord bot about catching cats.
# Copyright (C) 2026 Lia Milenakos & cattito Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import time

import discord

from shared import bot
from database import Blacklist


async def check_blacklist_slash(interaction: discord.Interaction) -> bool:
    """Check if a user/guild/channel is blacklisted. Returns True if blacklisted."""
    try:
        if await is_blacklisted(user_id=interaction.user.id):
            logging.warning(f"Blacklisted user {interaction.user.id} tried slash command {interaction.command.name}")
            await interaction.response.send_message("You are blacklisted from using this bot.", ephemeral=True)
            return True
        if interaction.guild and await is_blacklisted(guild_id=interaction.guild.id):
            logging.warning(f"Blacklisted guild {interaction.guild.id} tried slash command {interaction.command.name}")
            await interaction.response.send_message("This server is blacklisted from using this bot.", ephemeral=True)
            return True
        if await is_blacklisted(channel_id=interaction.channel.id):
            logging.warning(f"Blacklisted channel {interaction.channel.id} tried slash command {interaction.command.name}")
            await interaction.response.send_message("This channel is blacklisted from using this bot.", ephemeral=True)
            return True
    except Exception as e:
        logging.error(f"Error checking slash command blacklist: {e}")
    return False


async def is_blacklisted(user_id: int = None, guild_id: int = None, channel_id: int = None) -> bool:
    """Check if a user, guild, or channel is blacklisted"""
    try:
        if user_id:
            entry = await Blacklist.get_or_none(blacklist_type="user", target_id=user_id)
            return entry is not None
        elif guild_id:
            entry = await Blacklist.get_or_none(blacklist_type="guild", target_id=guild_id)
            return entry is not None
        elif channel_id:
            entry = await Blacklist.get_or_none(blacklist_type="channel", target_id=channel_id)
            return entry is not None
    except Exception as e:
        logging.error(f"Error checking blacklist: {e}")
    return False


async def add_to_blacklist(target_id: int, blacklist_type: str, reason: str, blacklisted_by: int) -> bool:
    """Add a user/guild/channel to blacklist"""
    try:
        existing = await Blacklist.get_or_none(blacklist_type=blacklist_type, target_id=target_id)
        if existing:
            return False
        await Blacklist.create(
            blacklist_type=blacklist_type,
            target_id=target_id,
            reason=reason,
            blacklisted_at=int(time.time()),
            blacklisted_by=blacklisted_by
        )
        return True
    except Exception as e:
        logging.error(f"Error adding to blacklist: {e}")
        return False


async def remove_from_blacklist(target_id: int, blacklist_type: str) -> bool:
    """Remove a user/guild/channel from blacklist"""
    try:
        entry = await Blacklist.get_or_none(blacklist_type=blacklist_type, target_id=target_id)
        if entry:
            await entry.delete()
            return True
        return False
    except Exception as e:
        logging.error(f"Error removing from blacklist: {e}")
        return False


async def get_blacklist_info(target_id: int, blacklist_type: str) -> dict:
    """Get info about a blacklist entry"""
    try:
        entry = await Blacklist.get_or_none(blacklist_type=blacklist_type, target_id=target_id)
        if entry:
            return {
                "id": entry.id,
                "type": entry.blacklist_type,
                "target_id": entry.target_id,
                "reason": entry.reason,
                "blacklisted_at": entry.blacklisted_at,
                "blacklisted_by": entry.blacklisted_by
            }
        return None
    except Exception as e:
        logging.error(f"Error getting blacklist info: {e}")
        return None


async def check_guild_blacklist(guild_id: int) -> bool:
    """Check if guild is blacklisted and leave if so"""
    try:
        if await is_blacklisted(guild_id=guild_id):
            try:
                guild = bot.get_guild(guild_id)
                if guild:
                    await guild.leave()
                    logging.warning(f"Left blacklisted guild {guild_id}")
            except Exception as e:
                logging.error(f"Error leaving blacklisted guild: {e}")
            return True
    except Exception as e:
        logging.error(f"Error checking guild blacklist: {e}")
    return False


async def check_message_blacklist(message: discord.Message) -> bool:
    """Check if user/guild/channel is blacklisted"""
    try:
        if await is_blacklisted(user_id=message.author.id):
            logging.warning(f"Blacklisted user {message.author.id} tried to use bot")
            return True
        if message.guild and await is_blacklisted(guild_id=message.guild.id):
            logging.warning(f"Blacklisted guild {message.guild.id} tried to use bot")
            return True
        if await is_blacklisted(channel_id=message.channel.id):
            logging.warning(f"Blacklisted channel {message.channel.id} tried to use bot")
            return True
    except Exception as e:
        logging.error(f"Error checking message blacklist: {e}")
    return False


async def global_interaction_check(interaction: discord.Interaction) -> bool:
    """Blacklist gate - runs before every app command"""
    from shared import bot as _b
    try:
        cmd_name = interaction.command.name if interaction.command else "?"
        if await is_blacklisted(user_id=interaction.user.id):
            logging.warning(f"Blacklisted user {interaction.user.id} tried /{cmd_name}")
            await interaction.response.send_message("You are blacklisted from using this bot.", ephemeral=True)
            return False
        if interaction.guild and await is_blacklisted(guild_id=interaction.guild.id):
            logging.warning(f"Blacklisted guild {interaction.guild.id} tried /{cmd_name}")
            await interaction.response.send_message("This server is blacklisted from using this bot.", ephemeral=True)
            return False
        if interaction.channel and await is_blacklisted(channel_id=interaction.channel.id):
            logging.warning(f"Blacklisted channel {interaction.channel.id} tried /{cmd_name}")
            await interaction.response.send_message("This channel is blacklisted from using this bot.", ephemeral=True)
            return False
    except Exception as e:
        logging.error(f"Blacklist check error: {e}")
    return True
