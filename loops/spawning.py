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

import asyncio, logging, random, time, math, re

import discord
from discord.ui import LayoutView, TextDisplay

import config
import shared
from shared import emojis, temp_spawns_storage
import shared
from constants import cattypes, type_dict, allowedemojis
from core.utils import get_emoji
from core.logging_setup import log_rain, log_catch
from database import Channel, Profile, User, Prism


async def spawn_cat(ch_id, localcat=None, force_spawn=None):
    try:
        channel = await Channel.get_or_none(channel_id=int(ch_id))
        if not channel:
            raise Exception
    except Exception:
        return False
    if channel.cat or channel.yet_to_spawn > time.time() + 10:
        return False

    if not localcat:
        localcat = random.choices(cattypes, weights=type_dict.values())[0]
    icon = get_emoji(localcat.lower() + "cat")
    file = discord.File(
        f"images/spawn/{localcat.lower()}_cat.png",
    )
    channeley = shared.bot.get_partial_messageable(int(ch_id))

    appearstring = '{emoji} {type} cat has appeared! Type "cat" to catch it!' if not channel.appear else channel.appear

    if int(ch_id) in temp_spawns_storage:
        return False

    temp_spawns_storage.append(int(ch_id))

    try:
        message_is_sus = await channeley.send(
            appearstring.replace("{emoji}", str(icon)).replace("{type}", localcat),
            file=file,
            allowed_mentions=discord.AllowedMentions.all(),
        )
    except discord.Forbidden:
        await channel.delete()
        temp_spawns_storage.remove(int(ch_id))
        return False
    except discord.NotFound:
        await channel.delete()
        temp_spawns_storage.remove(int(ch_id))
        return False
    except Exception:
        temp_spawns_storage.remove(int(ch_id))
        return False

    channel.cat = message_is_sus.id
    channel.yet_to_spawn = 0
    channel.forcespawned = bool(force_spawn)
    channel.cattype = localcat
    await channel.save()
    temp_spawns_storage.remove(int(ch_id))
    logging.debug("Cat spawned, forced: %s", bool(force_spawn))
    return True


async def rain_recovery_loop(channel):
    logging.debug("Rain started, cats %d", channel.cat_rains)
    while True:
        await asyncio.sleep(5)
        await channel.refresh_from_db()
        if channel.cat_rains <= 0:
            break
        if channel.cat_rains and not channel.cat and time.time() - channel.rain_should_end > 5:
            await spawn_cat(str(channel.channel_id))
            channel.cat_rains -= 1
            await channel.save()


async def rain_end(message, channel, force_summary=None):
    try:
        for _ in range(3):
            await message.channel.send("# :bangbang: cat rain has ended")
            await asyncio.sleep(0.4)
    except Exception:
        pass

    lock_success = False
    try:
        me_overwrites = message.channel.overwrites_for(message.guild.me)
        me_overwrites.send_messages = True

        everyone_overwrites = message.channel.overwrites_for(message.guild.default_role)
        current_perm = everyone_overwrites.send_messages
        everyone_overwrites.send_messages = False

        await asyncio.gather(
            message.channel.set_permissions(message.guild.default_role, overwrite=everyone_overwrites),
            message.channel.set_permissions(message.guild.me, overwrite=me_overwrites),
        )
        lock_success = True
    except Exception:
        pass

    await asyncio.sleep(1)

    # rain summary
    try:
        rain_server = force_summary
        if not rain_server:
            if channel.channel_id not in config.rain_starter or channel.channel_id not in config.cat_cought_rain:
                return
            rain_server = config.cat_cought_rain[channel.channel_id]

        # you can throw out the name of the emoji to save on characters
        pack_names = ["Christmas", "Wooden", "Stone", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Celestial"]
        pack_yeah = {"Christmas": 1.2, "Wooden": 1, "Stone": 0.9, "Bronze": 0.8, "Silver": 0.7, "Gold": 0.6, "Platinum": 0.5, "Diamond": 0.4, "Celestial": 0.3}
        rain_packs = []
        rain_cats = []

        for key in rain_server.keys():
            if key in cattypes:
                rain_cats.append(key)
            if key in pack_names:
                rain_packs.append(key)

        funny_cat_emojis = {k: re.sub(r":[A-Za-z0-9_]*:", ":i:", get_emoji(k.lower() + "cat"), count=1) for k in rain_cats}
        funny_pack_emojis = {k: re.sub(r":[A-Za-z0-9_]*:", ":i:", get_emoji(k.lower() + "pack"), count=1) for k in rain_packs}

        funny_emojis = funny_cat_emojis | funny_pack_emojis

        reverse_mapping = {}

        for thing_type, user_ids in rain_server.items():
            for user_id in user_ids:
                if user_id not in reverse_mapping:
                    reverse_mapping[user_id] = []
                reverse_mapping[user_id].append(thing_type)

        evil_types = []
        epic_fail = False
        thingtypes = cattypes + pack_names
        for cat_type in thingtypes:
            part_one = "## Rain Summary\n"

            for user_id, cat_types in sorted(reverse_mapping.items(), key=lambda item: len(item[1]), reverse=True):
                show_cats = ""
                shortened_types = False
                dictdict = type_dict | pack_yeah
                cat_types.sort(reverse=True, key=lambda x: dictdict[x])
                pack_amount = 0
                for cat_type_two in cat_types:
                    if cat_type_two in evil_types:
                        shortened_types = True
                        continue
                    if cat_type_two in pack_names:
                        pack_amount += 1
                    show_cats += funny_emojis[cat_type_two]
                if show_cats != "":
                    if shortened_types:
                        show_cats = ": ..." + show_cats
                    else:
                        show_cats = ": " + show_cats
                if str(config.rain_starter[channel.channel_id]) in str(user_id):
                    part_one += "☔ "
                disambig = f"({len(cat_types)})"
                if pack_amount:
                    disambig = f"({len(cat_types) - pack_amount} {get_emoji('finecat')}, {pack_amount} {get_emoji('woodenpack')})"
                part_one += f"{user_id} {disambig}{show_cats}\n"

            if not lock_success and not epic_fail:
                part_one += "-# 💡 cattito will automatically lock the channel for a few seconds after a rain if you give it `Manage Permissions`"

            if len(part_one) > 4000:
                evil_types.append(cat_type)
                epic_fail = True
                continue

            parts = [part_one]

            if epic_fail:
                part_two = ""
                for cat_type in thingtypes:
                    if cat_type not in rain_server.keys():
                        continue
                    if len(rain_server[cat_type]) > 5:
                        part_two += f"{funny_emojis[cat_type]} *{len(rain_server[cat_type])} catches*\n"
                    else:
                        part_two += f"{funny_emojis[cat_type]} {' '.join(rain_server[cat_type])}\n"

                if not lock_success:
                    part_two += "-# 💡 cattito will automatically lock the channel for a few seconds after a rain if you give it `Manage Permissions`"

                parts.append(part_two)

            for rain_msg in parts:
                if ":i:" not in rain_msg:
                    continue
                # this is to bypass character limit up to 4k
                v = LayoutView()
                v.add_item(TextDisplay(rain_msg))
                try:
                    await message.channel.send(view=v)
                except Exception:
                    pass

            break

        # --- Rain end log ---
        try:
            total_catches = sum(len(v) for v in rain_server.values())
            unique_catchers = len(set(uid for uids in rain_server.values() for uid in uids))
            starter_id = config.rain_starter.get(channel.channel_id, "?")
            rain_end_embed = discord.Embed(
                title="🛑 Rain Ended",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            rain_end_embed.add_field(name="Channel", value=str(channel.channel_id), inline=True)
            rain_end_embed.add_field(name="Started By", value=f"<@{starter_id}>", inline=True)
            rain_end_embed.add_field(name="Total Catches", value=str(total_catches), inline=True)
            rain_end_embed.add_field(name="Unique Catchers", value=str(unique_catchers), inline=True)
            await log_rain(rain_end_embed)
        except Exception as log_err:
            logging.warning(f"Rain end log failed: {log_err}")

        del config.cat_cought_rain[channel.channel_id]
        del config.rain_starter[channel.channel_id]

        await asyncio.sleep(2)
    except discord.Forbidden:
        pass
    finally:
        if lock_success:
            everyone_overwrites = message.channel.overwrites_for(message.guild.default_role)
            everyone_overwrites.send_messages = current_perm
            await message.channel.set_permissions(message.guild.default_role, overwrite=everyone_overwrites)
