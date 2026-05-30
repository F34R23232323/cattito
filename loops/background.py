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

import asyncio, datetime, logging, random, time

import aiohttp, discord
from discord.ui import Button, LayoutView

import config
import shared
from shared import (
    bot,
    loop_count,
    last_loop_time,
    reactions_ratelimit,
    pointlaugh_ratelimit,
    catchcooldown,
    fakecooldown,
    temp_cookie_storage,
    temp_belated_storage,
)
from constants import VIEW_TIMEOUT, vote_button_texts, battle, news_list
from core.colors import Colors
from core.utils import get_emoji, fetch_dm_channel, get_streak_reward, postpone_reminder
from database import Channel, User, Profile, Prism, Reminder
from loops.spawning import spawn_cat
from achievements import refresh_quests


async def background_loop():
    global pointlaugh_ratelimit, reactions_ratelimit, last_loop_time, loop_count, catchcooldown, temp_belated_storage, temp_cookie_storage, fakecooldown
    pointlaugh_ratelimit = {}
    reactions_ratelimit = {}
    catchcooldown = {}
    fakecooldown = {}
    await bot.change_presence(activity=discord.CustomActivity(name=f"catting in {len(bot.guilds):,} servers 67"))

    # update cookies
    temp_temp_cookie_storage = temp_cookie_storage.copy()
    cookie_updates = []
    for cookie_id, cookies in temp_temp_cookie_storage.items():
        p = await Profile.get_or_create(guild_id=cookie_id[0], user_id=cookie_id[1])
        p.cookies = cookies
        cookie_updates.append(p)
    if cookie_updates:
        await Profile.bulk_update(cookie_updates, "cookies")
    logging.debug("Cookies updated: %d", len(cookie_updates))
    temp_cookie_storage = {}

    # temp_belated_storage cleanup
    # clean up anything older than 1 minute
    baseflake = discord.utils.time_snowflake(discord.utils.utcnow() - datetime.timedelta(minutes=1))
    for id in temp_belated_storage.copy().keys():
        if id < baseflake:
            del temp_belated_storage[id]

    if config.TOP_GG_TOKEN:
        async with aiohttp.ClientSession() as session:
            try:
                if not config.MIN_SERVER_SEND or len(bot.guilds) > config.MIN_SERVER_SEND:
                    # send server count to top.gg
                    r = await session.post(
                        f"https://top.gg/api/bots/{bot.user.id}/stats",
                        headers={"Authorization": config.TOP_GG_TOKEN},
                        json={"server_count": len(bot.guilds)},
                    )
                    r.close()

                # post commands to top.gg
                r = await session.post(
                    "https://top.gg/api/v1/projects/@me/commands",
                    headers={"Authorization": config.TOP_GG_TOKEN},
                    json=[command.to_dict(bot.tree) for command in bot.tree._get_all_commands(guild=None) if command.to_dict(bot.tree)["type"] == 1],
                )
                r.close()

            except Exception:
                logging.warning("Posting to top.gg failed.")


    # revive dead catch loops
    counter = 0
    async for channel in Channel.limit(["channel_id"], "yet_to_spawn < $1 AND cat = 0", time.time(), refetch=False):
        counter += 1
        await spawn_cat(str(channel.channel_id))
        await asyncio.sleep(0.1)
    logging.debug("Channels revived: %d", counter)

    # THIS IS CONSENTUAL AND TURNED OFF BY DEFAULT DONT BAN ME
    #
    # i wont go into the details of this because its a complicated mess which took me like solid 30 minutes of planning
    #
    # vote reminders
    reminder_count = 0
    start_time = int(time.time())
    while True:
        user = await User.collect(
            f"vote_time_topgg != 0 AND vote_time_topgg + 43200 < {start_time} AND reminder_vote != 0 AND reminder_vote < {start_time} "
            + 'AND EXISTS(SELECT 1 FROM profile WHERE profile.user_id = "user".user_id AND reminders_enabled = true) LIMIT 1',
        )
        if not user or not user[0]:
            break
        user = user[0]
        await asyncio.sleep(0.2)

        view = LayoutView(timeout=VIEW_TIMEOUT)
        button = Button(
            emoji=get_emoji("topgg"),
            label=random.choice(vote_button_texts),
            url="https://top.gg/bot/1387860417706987590/vote",
        )
        view.add_item(button)

        button = Button(label="Postpone", custom_id="vote")
        button.callback = postpone_reminder
        view.add_item(button)

        try:
            user_dm = await fetch_dm_channel(user)
            await user_dm.send("You can vote now!" if user.vote_streak < 10 else f"Vote now to keep your {user.vote_streak} streak going!", view=view)
        except Exception:
            pass

        # no repeat reminers for now
        user.reminder_vote = 0
        reminder_count += 1
        await user.save()

    logging.debug("Reminders sent: %d, type: %s", reminder_count, "vote")

    # i know the next two are similiar enough to be merged but its currently dec 30 and i cant be bothered
    # catch reminders
    reminder_count = 0
    while True:
        user = await Profile.collect(
            f"(reminders_enabled = true AND reminder_catch != 0) AND ((catch_cooldown != 0 AND catch_cooldown + 43200 < {start_time}) OR (reminder_catch > 1 AND reminder_catch < {start_time})) LIMIT 1",
        )
        if not user or not user[0]:
            break
        user = user[0]
        await asyncio.sleep(0.2)

        await refresh_quests(user)
        await user.refresh_from_db()

        quest_data = battle["quests"]["catch"][user.catch_quest]

        embed = discord.Embed(
            title=f"{get_emoji(quest_data['emoji'])} {quest_data['title']}",
            description=f"Reward: **{user.catch_reward}** XP",
            color=Colors.green,
        )

        view = LayoutView(timeout=VIEW_TIMEOUT)
        button = Button(label="Postpone", custom_id=f"catch_{user.guild_id}")
        button.callback = postpone_reminder
        view.add_item(button)

        guild = bot.get_guild(user.guild_id)
        if not guild:
            guild_name = "a server"
        else:
            guild_name = guild.name

        try:
            user_user = await User.get_or_create(id=user.user_id)
            user_dm = await fetch_dm_channel(user_user)
            await user_dm.send(f"A new quest is available in {guild_name}!", embed=embed, view=view)
        except Exception:
            pass
        user.reminder_catch = 0
        reminder_count += 1
        await user.save()

    logging.debug("Reminders sent: %d, type: %s", reminder_count, "catch")

    # misc reminders
    reminder_count = 0
    while True:
        user = await Profile.collect(
            f"(reminders_enabled = true AND reminder_misc != 0) AND ((misc_cooldown != 0 AND misc_cooldown + 43200 < {start_time}) OR (reminder_misc > 1 AND reminder_misc < {start_time})) LIMIT 1",
        )
        if not user or not user[0]:
            break
        user = user[0]
        await asyncio.sleep(0.2)

        await refresh_quests(user)
        await user.refresh_from_db()

        quest_data = battle["quests"]["misc"][user.misc_quest]

        embed = discord.Embed(
            title=f"{get_emoji(quest_data['emoji'])} {quest_data['title']}",
            description=f"Reward: **{user.misc_reward}** XP",
            color=Colors.green,
        )

        view = LayoutView(timeout=VIEW_TIMEOUT)
        button = Button(label="Postpone", custom_id=f"misc_{user.guild_id}")
        button.callback = postpone_reminder
        view.add_item(button)

        guild = bot.get_guild(user.guild_id)
        if not guild:
            guild_name = "a server"
        else:
            guild_name = guild.name

        try:
            user_user = await User.get_or_create(user_id=user.user_id)
            user_dm = await fetch_dm_channel(user_user)
            await user_dm.send(f"A new quest is available in {guild_name}!", embed=embed, view=view)
        except Exception:
            pass
        user.reminder_misc = 0
        reminder_count += 1
        await user.save()

    logging.debug("Reminders sent: %d, type: %s", reminder_count, "misc")

    # manual reminders
    async for reminder in Reminder.filter("time < $1", time.time()):
        try:
            user = await User.get_or_create(user_id=reminder.user_id)
            user_dm = await fetch_dm_channel(user)
            await user_dm.send(reminder.text)
            await asyncio.sleep(0.5)
        except Exception:
            pass
        await reminder.delete()
