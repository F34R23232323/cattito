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
import logging
import math
import random
import time
from typing import Optional

import discord
from discord import ButtonStyle
from discord.ui import Button, LayoutView, TextDisplay, Container, Section, Thumbnail, ActionRow

import shared
import shared
from constants import cattypes, type_dict, battle, rain_shill, news_list, VIEW_TIMEOUT
from core.colors import Colors
from core.utils import get_emoji, do_funny, fetch_dm_channel, get_streak_reward
from database import Profile, User
from achievements import refresh_quests, progress, achemb
from gui.components import Container as CustomContainer


@shared.bot.tree.command(description="why would anyone think a cattlepass would be a good idea")
async def battlepass(message: discord.Interaction):
    current_mode = ""
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    global_user = await User.get_or_create(user_id=message.user.id)

    async def toggle_reminders(interaction: discord.Interaction):
        nonlocal current_mode
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        await user.refresh_from_db()
        if not user.reminders_enabled:
            try:
                dm_channel = await fetch_dm_channel(global_user)
                await dm_channel.send(
                    f"You have enabled reminders in {interaction.guild.name}. You can disable them in the /battlepass command in that server or by saying `disable {interaction.guild.id}` here any time."
                )
            except Exception:
                await interaction.followup.send(
                    "Failed. Ensure you have DMs open by going to Server > Privacy Settings > Allow direct messages from server members."
                )
                return

        user.reminders_enabled = not user.reminders_enabled
        await user.save()

        view = LayoutView(timeout=VIEW_TIMEOUT)
        button = Button(emoji="🔄", label="Refresh", style=ButtonStyle.blurple)
        button.callback = gen_main
        view.add_item(button)

        if user.reminders_enabled:
            button = Button(emoji="🔕", style=ButtonStyle.blurple)
        else:
            button = Button(label="Enable Reminders", emoji="🔔", style=ButtonStyle.green)
        button.callback = toggle_reminders
        view.add_item(button)

        await interaction.followup.send(
            f"Reminders are now {'enabled' if user.reminders_enabled else 'disabled'}.",
            ephemeral=True,
        )
        await interaction.edit_original_response(view=view)

    async def gen_main(interaction, first=False):
        nonlocal current_mode
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        await interaction.response.defer()
        current_mode = "Main"

        await refresh_quests(user)

        await global_user.refresh_from_db()
        if global_user.vote_time_topgg + 12 * 3600 > time.time():
            await progress(message, user, "vote")
            await global_user.refresh_from_db()

        await user.refresh_from_db()

        now = discord.utils.utcnow() + datetime.timedelta(hours=4)

        if now.month == 12:
            next_month = datetime.datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime.datetime(now.year, now.month + 1, 1)

        next_month -= datetime.timedelta(hours=4)

        timestamp = int(time.mktime(next_month.timetuple()))

        description = f"Season ends <t:{timestamp}:R>\n\n"

        streak_string = ""
        if global_user.vote_streak >= 5:
            streak_string = f" (🔥 {global_user.vote_streak}x streak)"
        if user.vote_cooldown != 0:
            description += f"✅ ~~Vote on Top.gg~~\n- Refreshes <t:{int(user.vote_cooldown + 12 * 3600)}:R>{streak_string}\n"
        else:
            is_weekend = now.weekday() >= 4

            if is_weekend:
                description += "-# *Double Vote XP During Weekends*\n"

            description += f"{get_emoji('topgg')} [Vote on Top.gg](https://top.gg/bot/1387860417706987590/vote)\n"

            if is_weekend:
                description += f"- Reward: ~~{user.vote_reward}~~ **{user.vote_reward * 2}** XP"
            else:
                description += f"- Reward: {user.vote_reward} XP"

            next_streak_data = get_streak_reward(global_user.vote_streak + 1)
            if next_streak_data["reward"] and global_user.vote_time_topgg + 24 * 3600 > time.time():
                description += f" + {next_streak_data['emoji']} 1 {next_streak_data['reward'].capitalize()} pack"

            description += f"{streak_string}\n"

        if user.catch_quest and user.catch_quest in battle["quests"]["catch"]:
            catch_quest = battle["quests"]["catch"][user.catch_quest]
            if user.catch_cooldown != 0:
                description += f"\u2705 ~~{catch_quest['title']}~~\n- Refreshes <t:{int(user.catch_cooldown + 12 * 3600 if user.catch_cooldown + 12 * 3600 < timestamp else timestamp)}:R>\n"
            else:
                progress_string = ""
                if catch_quest["progress"] != 1:
                    if user.catch_quest == "finenice":
                        try:
                            real_progress = ["need both", "need Nice", "need Fine", "done"][user.catch_progress]
                        except IndexError:
                            real_progress = "error"
                        progress_string = f" ({real_progress})"
                    else:
                        progress_string = f" ({user.catch_progress}/{catch_quest['progress']})"
                description += f"{get_emoji(catch_quest['emoji'])} {catch_quest['title']}{progress_string}\n- Reward: {user.catch_reward} XP\n"
        else:
            description += "\u23f3 Catch quest loading...\n"

        if user.misc_quest and user.misc_quest in battle["quests"]["misc"]:
            misc_quest = battle["quests"]["misc"][user.misc_quest]
            if user.misc_cooldown != 0:
                description += f"\u2705 ~~{misc_quest['title']}~~\n- Refreshes <t:{int(user.misc_cooldown + 12 * 3600 if user.misc_cooldown + 12 * 3600 < timestamp else timestamp)}:R>\n"
            else:
                progress_string = ""
                if misc_quest["progress"] != 1:
                    progress_string = f" ({user.misc_progress}/{misc_quest['progress']})"
                description += f"{get_emoji(misc_quest['emoji'])} {misc_quest['title']}{progress_string}\n- Reward: {user.misc_reward} XP\n"
        else:
            description += "\u23f3 Misc quest loading...\n"

        if user.extra1_quest and user.extra1_quest in battle["quests"]["extra1"]:
            extra1_quest = battle["quests"]["extra1"][user.extra1_quest]
            if user.extra1_cooldown != 0:
                description += f"✅ ~~{extra1_quest['title']}~~\n- Refreshes <t:{int(user.extra1_cooldown + 12 * 3600 if user.extra1_cooldown + 12 * 3600 < timestamp else timestamp)}:R>\n"
            else:
                progress_string = ""
                if extra1_quest["progress"] != 1:
                    progress_string = f" ({user.extra1_progress}/{extra1_quest['progress']})"
                description += f"{get_emoji(extra1_quest['emoji'])} {extra1_quest['title']}{progress_string}\n- Reward: {user.extra1_reward} XP\n"
        elif user.extra1_quest:
            description += "⏳ Extra quest loading...\n"

        if user.extra2_quest and user.extra2_quest in battle["quests"]["extra2"]:
            extra2_quest = battle["quests"]["extra2"][user.extra2_quest]
            if user.extra2_cooldown != 0:
                description += f"✅ ~~{extra2_quest['title']}~~\n- Refreshes <t:{int(user.extra2_cooldown + 12 * 3600 if user.extra2_cooldown + 12 * 3600 < timestamp else timestamp)}:R>\n\n"
            else:
                progress_string = ""
                if extra2_quest["progress"] != 1:
                    progress_string = f" ({user.extra2_progress}/{extra2_quest['progress']})"
                description += f"{get_emoji(extra2_quest['emoji'])} {extra2_quest['title']}{progress_string}\n- Reward: {user.extra2_reward} XP\n\n"
        elif user.extra2_quest:
            description += "⏳ Extra quest loading...\n\n"

        if user.battlepass >= len(battle["seasons"][str(user.season)]):
            description += f"**Extra Rewards** [{user.progress}/1500 XP]\n"
            colored = int(user.progress / 150)
            description += get_emoji("staring_square") * colored + "⬛" * (10 - colored) + "\nReward: " + get_emoji("stonepack") + " Stone pack\n\n"
        else:
            level_data = battle["seasons"][str(user.season)][user.battlepass]
            description += f"**Level {user.battlepass + 1}/30** [{user.progress}/{level_data['xp']} XP]\n"
            colored = int(user.progress / level_data["xp"] * 10)
            description += f"**{user.battlepass}** " + get_emoji("staring_square") * colored + "⬛" * (10 - colored) + f" **{user.battlepass + 1}**\n"

            if level_data["reward"] == "Rain":
                description += f"Reward: ☔ {level_data['amount']} minutes of rain\n\n"
            elif level_data["reward"] in cattypes:
                description += f"Reward: {get_emoji(level_data['reward'].lower() + 'cat')} {level_data['amount']} {level_data['reward']} cats\n\n"
            else:
                description += f"Reward: {get_emoji(level_data['reward'].lower() + 'pack')} {level_data['reward']} pack\n\n"

        levels = battle["seasons"][str(user.season)]
        for num, level_data in enumerate(levels):
            claimed_suffix = "_claimed" if num < user.battlepass else ""
            if level_data["reward"] == "Rain":
                description += get_emoji(str(level_data["amount"]) + "rain" + claimed_suffix)
            elif level_data["reward"] in cattypes:
                description += get_emoji(level_data["reward"].lower() + "cat" + claimed_suffix)
            else:
                description += get_emoji(level_data["reward"].lower() + "pack" + claimed_suffix)
            if num % 10 == 9:
                description += "\n"
        if user.battlepass >= len(battle["seasons"][str(user.season)]) - 1:
            description += f"*Extra:* {get_emoji('stonepack')} per 1500 XP"

        embedVar = discord.Embed(
            title=f"Cattlepass Season {user.season}",
            description=description,
            color=Colors.brown,
        ).set_footer(text=rain_shill)
        view = LayoutView(timeout=VIEW_TIMEOUT)

        button = Button(emoji="🔄", label="Refresh", style=ButtonStyle.blurple)
        button.callback = gen_main
        view.add_item(button)

        if user.reminders_enabled:
            button = Button(emoji="🔕", style=ButtonStyle.blurple)
        else:
            button = Button(label="Enable Reminders", emoji="🔔", style=ButtonStyle.green)
        button.callback = toggle_reminders
        view.add_item(button)

        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state.strip()[-4:]:
            embedVar.set_author(name="You have unread news! /news")

        if first:
            await interaction.followup.send(embed=embedVar, view=view)
        else:
            await interaction.edit_original_response(embed=embedVar, view=view)

    await gen_main(message, True)
