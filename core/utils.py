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

import asyncio
import datetime
import math
import random
import time
from typing import Optional

import aiohttp
import discord
import emoji
import unidecode

import config
import shared
from shared import bot
from constants import type_dict, cattypes, prism_names, pack_data, cattype_lc_dict, allowedemojis, testers
from constants import ach_list, ach_names, ach_titles, battle, catnip_list, news_list
from constants import VIEW_TIMEOUT, EXTRA_QUEST_TRIGGERS, NONOWORDS, funny, rain_shill, hints, vote_button_texts, cat_facts_list
from constants import total_commands_used
from core.colors import Colors
from database import Channel, Prism, Profile, Reminder, Server, User, Blacklist


def get_emoji(name):
    if name in shared.emojis:
        return shared.emojis[name]
    elif name in emoji.EMOJI_DATA:
        return name
    else:
        return "\U0001f533"


async def fetch_dm_channel(user: User) -> discord.PartialMessageable:
    if user.dm_channel_id:
        return bot.get_partial_messageable(user.dm_channel_id)
    else:
        person = await bot.fetch_user(user.user_id)
        if not person.dm_channel:
            await person.create_dm()
        user.dm_channel_id = person.dm_channel.id
        await user.save()
        return person.dm_channel


def format_timedelta(start_timestamp, end_timestamp):
    delta = datetime.timedelta(seconds=end_timestamp - start_timestamp)
    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{days}d {hours}h {minutes}m {seconds}s"


# converts string to lowercase alphanumeric characters only
def alnum(string):
    return "".join(item for item in string.lower() if item.isalnum())


# function to autocomplete cat_type choices
async def cat_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [discord.app_commands.Choice(name=choice, value=choice) for choice in cattypes if current.lower() in choice.lower()][:25]


# function to autocomplete /cat, it only shows the cats you have
async def cat_command_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    choices = []
    for choice in cattypes:
        if current.lower() in choice.lower() and user[f"cat_{choice}"] > 0:
            choices.append(discord.app_commands.Choice(name=choice, value=choice))
    return choices[:25]


async def lb_type_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [
        discord.app_commands.Choice(name=choice, value=choice)
        for choice in ["All"] + await cats_in_server(interaction.guild_id)
        if current.lower() in choice.lower()
    ][:25]


async def cats_in_server(guild_id):
    return [cat_type for cat_type in cattypes if (await Profile.count(f'guild_id = $1 AND "cat_{cat_type}" > 0 LIMIT 1', guild_id))]


# function to autocomplete cat_type choices for /gift
async def gift_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
    actual_user = await User.get_or_create(user_id=interaction.user.id)
    choices = []
    for choice in cattypes:
        if current.lower() in choice.lower() and user[f"cat_{choice}"] > 0:
            choices.append(discord.app_commands.Choice(name=f"{choice} (x{user[f'cat_{choice}']})", value=choice))
    if current.lower() in "rain" and actual_user.rain_minutes > 0:
        choices.append(discord.app_commands.Choice(name=f"Rain ({actual_user.rain_minutes} minutes)", value="rain"))
    for choice in pack_data:
        if user[f"pack_{choice['name'].lower()}"] > 0:
            pack_name = choice["name"]
            pack_amount = user[f"pack_{pack_name.lower()}"]
            choices.append(discord.app_commands.Choice(name=f"{pack_name} pack (x{pack_amount})", value=pack_name.lower()))
    return choices[:25]


# function to autocomplete achievement choice for /giveachievement
async def ach_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    return [
        discord.app_commands.Choice(name=val["title"], value=key)
        for (key, val) in ach_list.items()
        if (alnum(current) in alnum(key) or alnum(current) in alnum(val["title"]))
    ][:25]


async def do_funny(message):
    await message.response.send_message(random.choice(funny), ephemeral=True)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    user.funny += 1
    await user.save()
    from achievements import achemb
    await achemb(message, "curious", "reply")
    if user.funny >= 50:
        from achievements import achemb
        await achemb(message, "its_not_working", "followup")


def get_streak_reward(streak):
    if streak % 5 != 0 or streak in [0, 5]:
        return {"reward": None, "emoji": "\u2b1b", "done_emoji": "\U0001f7e6"}
    pack_type = "gold"
    if streak % 100 == 0:
        pack_type = "diamond"
    elif streak % 25 == 0:
        pack_type = "platinum"
    return {"reward": pack_type, "emoji": get_emoji(f"{pack_type}pack"), "done_emoji": get_emoji(f"{pack_type}pack_claimed")}


async def postpone_reminder(interaction):
    reminder_type = interaction.data["custom_id"]
    if reminder_type == "vote":
        user = await User.get_or_create(user_id=interaction.user.id)
        user.reminder_vote = int(time.time()) + 30 * 60
        await user.save()
    else:
        guild_id = reminder_type.split("_")[1]
        user = await Profile.get_or_create(guild_id=int(guild_id), user_id=interaction.user.id)
        if reminder_type.startswith("catch"):
            user.reminder_catch = int(time.time()) + 30 * 60
        else:
            user.reminder_misc = int(time.time()) + 30 * 60
        await user.save()
    await interaction.response.send_message(f"ok, i will remind you <t:{int(time.time()) + 30 * 60}:R>", ephemeral=True)
