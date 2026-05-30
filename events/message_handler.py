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
import io
import logging
import math
import os
import random
import re
import time
import traceback

import aiohttp
import discord
import unidecode
from PIL import Image

import config
import shared
from shared import OWNER_IDS, emojis, reactions_ratelimit, pointlaugh_ratelimit
from shared import temp_catches_storage, temp_belated_storage, temp_cookie_storage
from shared import catchcooldown, fakecooldown, last_loop_time, RAIN_ID, vote_server
from shared import _ac_data
from constants import cattypes, type_dict, allowedemojis, pack_data, cattype_lc_dict, NONOWORDS, VIEW_TIMEOUT
from constants import hints, vote_button_texts, catnip_list, total_commands_used
from core.colors import Colors
from core.utils import get_emoji, do_funny, fetch_dm_channel, get_streak_reward, postpone_reminder
from core.logging_setup import log_rain, log_catch, log_prefix, log_dev, log_error, log_command, log_uptime
from database import Channel, Server, Profile, User, Prism, Reminder, Blacklist
from systems.blacklist import check_message_blacklist, is_blacklisted, add_to_blacklist, remove_from_blacklist, get_blacklist_info, check_guild_blacklist
from systems.anticheat import _ac_record_catch, _ac_send_report
from loops.spawning import spawn_cat, rain_recovery_loop, rain_end
from loops.background import background_loop
from achievements import achemb, progress
from catnip.bounties import bounty
from loops.backup import do_backup


async def on_message_dev_commands(message: discord.Message):
    if not message.content.startswith("cat!"):
        return

    if message.author.id not in OWNER_IDS:
        return

    text = message.content.strip()

    async def log_dev_cmd(result: str = ""):
        try:
            guild_str = f"{message.guild.name} ({message.guild.id})" if message.guild else "DM"
            embed = discord.Embed(
                title="\U0001f6e0\ufe0f Dev Command",
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Dev", value=f"{message.author} ({message.author.id})", inline=True)
            embed.add_field(name="Server", value=guild_str, inline=True)
            embed.add_field(name="Command", value=f"```{text[:500]}```", inline=False)
            if result:
                embed.add_field(name="Result", value=result[:500], inline=False)
            await log_prefix(embed)
        except Exception as e:
            logging.warning(f"Dev command log failed: {e}")

    if text.lower() in ("cat!devhelp", "cat!commands"):
        embed = discord.Embed(title="Dev Commands", color=Colors.brown)
        cmds = [
            ("cat!devhelp", "Show this list"),
            ("cat!stoprain", "Stop rain in current channel"),
            ("cat!rainstatus", "Check rain status in current channel"),
            ("cat!blacklist user/guild/channel <id> [reason]", "Blacklist a target"),
            ("cat!unblacklist user/guild/channel <id>", "Remove from blacklist"),
            ("cat!blacklist view user/guild/channel", "View blacklist entries"),
            ("cat!sync [guild|clear]", "Sync slash commands (guild=instant, global=1hr)"),
            ("cat!forcespawn [channel_id]", "Force a cat to spawn"),
            ("cat!give <user_id> <amount>", "Give cats to a user (all servers)"),
            ("cat!userinfo <user_id>", "View a user's profile data"),
            ("cat!announce <message>", "Send message to all setup channels"),
            ("cat!sweep", "Remove active cat from current channel (in on_message)"),
            ("cat!devbackup", "Manually trigger a DB backup"),
            ("cat!devrain <user_id> <amount>", "Give rain minutes to a user"),
            ("cat!devsay [#channel_id] <message>", "Make the bot send a message in a channel"),
            ("cat!devembed [#channel_id] <title> | <desc> [| #color]", "Make the bot send a rich embed"),
            ("cat!devserverinfo <guild_id>", "Get detailed info about any server"),
            ("cat!devsetcustom <user_id> <cat_name|none>", "Set a user's custom cat"),
            ("cat!rain <user_id> short/medium/long/N", "Give rain minutes to a user"),
            ("cat!rain give <user_id> <amount>", "Give rain minutes to a user"),
            ("cat!rain remove <user_id> <amount>", "Remove rain minutes from a user"),
            ("cat!restart [db]", "Reload the bot (add 'db' to also reload DB)"),
            ("cat!eval <code>", "Execute async code"),
            ("cat!print <expr>", "Evaluate and print an expression"),
            ("cat!news <message>", "Send message to ALL channels (use announce instead)"),
            ("cat!custom <user_id> <cat_name>", "Set a user's custom cat"),
        ]
        for name, desc in cmds:
            embed.add_field(name=f"`{name}`", value=desc, inline=False)
        await message.reply(embed=embed)
        return

    if text.lower().startswith("cat!stoprain"):
        channel = await Channel.get_or_none(channel_id=message.channel.id)
        if not channel:
            await message.reply("This channel is not setup.")
            return

        if channel.cat_rains <= 0:
            await message.reply("No active rain in this channel.")
            return

        old_rain_count = channel.cat_rains
        channel.cat_rains = 0
        channel.yet_to_spawn = 0
        await channel.save()

        await message.reply(f"\u2705 Stopped rain! ({old_rain_count} cats remaining were canceled)")
        logging.info(f"Rain stopped in channel {message.channel.id} by {message.author} (was {old_rain_count} cats left)")

        try:
            rain_stop_embed = discord.Embed(
                title="\U0001f6d1 Rain Stopped",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            rain_stop_embed.add_field(name="Channel", value=f"#{message.channel.name} ({message.channel.id})", inline=True)
            rain_stop_embed.add_field(name="Cats Canceled", value=str(old_rain_count), inline=True)
            rain_stop_embed.add_field(name="Stopped By", value=f"{message.author} ({message.author.id})", inline=False)
            rain_stop_embed.set_footer(text=f"Total Servers: {len(shared.bot.guilds)}")
            await log_rain(rain_stop_embed)
        except Exception as log_err:
            logging.warning(f"Rain stop log failed: {log_err}")
        await log_dev_cmd(f"Stopped rain \u2014 {old_rain_count} cats canceled in #{message.channel.name}")

    elif text.lower().startswith("cat!servers"):
        parts = text.split(None, 2)
        search = parts[1] if len(parts) > 1 else None

        guilds = list(shared.bot.guilds)
        if search:
            guilds = [g for g in guilds if str(g.id) == search or str(g.owner_id) == search]

        if not guilds:
            await message.reply("No servers found with that ID or owner ID.")
            return

        total = len(guilds)
        page_size = 10
        BAR_LENGTH = 20

        loading_embed = discord.Embed(
            title="\u23f3 Loading servers...",
            description=f"`{'\\u2591' * BAR_LENGTH}` 0%",
            color=discord.Color.orange()
        )
        loading_msg = await message.reply(embed=loading_embed)

        pages = []
        for i in range(0, total, page_size):
            chunk = guilds[i:i + page_size]
            embed = discord.Embed(
                title=f"\U0001f4dc Bot Servers ({i+1}\u2013{i+len(chunk)} of {total})",
                color=discord.Color.green()
            )
            for g in chunk:
                try:
                    invite = await g.text_channels[0].create_invite(max_age=0, max_uses=0)
                    invite_str = f"[Invite]({invite.url})"
                except Exception:
                    invite_str = "No permissions \u274c"
                embed.add_field(
                    name=g.name,
                    value=f"\U0001f194 `{g.id}`\n\U0001f451 `{g.owner_id}`\n\U0001f517 {invite_str}",
                    inline=False
                )
            pages.append(embed)

            progress_val = min(i + page_size, total)
            percent = int((progress_val / total) * 100)
            filled = int((progress_val / total) * BAR_LENGTH)
            bar = "\u2588" * filled + "\u2591" * (BAR_LENGTH - filled)
            loading_embed.description = f"`{bar}` {percent}%"
            try:
                await loading_msg.edit(embed=loading_embed)
            except Exception:
                pass

        current = [0]

        def make_view():
            from discord.ui import Button, LayoutView
            view = LayoutView(timeout=600)
            prev_btn = Button(label="\u2b05\ufe0f", style=discord.ButtonStyle.secondary, disabled=len(pages) <= 1)
            next_btn = Button(label="\u27a1\ufe0f", style=discord.ButtonStyle.secondary, disabled=len(pages) <= 1)

            async def prev_page(interaction: discord.Interaction):
                if interaction.user.id not in OWNER_IDS:
                    await interaction.response.send_message("nope", ephemeral=True)
                    return
                current[0] = (current[0] - 1) % len(pages)
                await interaction.response.edit_message(embed=pages[current[0]], view=make_view())

            async def next_page(interaction: discord.Interaction):
                if interaction.user.id not in OWNER_IDS:
                    await interaction.response.send_message("nope", ephemeral=True)
                    return
                current[0] = (current[0] + 1) % len(pages)
                await interaction.response.edit_message(embed=pages[current[0]], view=make_view())

            prev_btn.callback = prev_page
            next_btn.callback = next_page
            view.add_item(prev_btn)
            view.add_item(next_btn)
            return view

        loading_embed.title = f"\u2705 Loaded {total} server(s)"
        loading_embed.description = f"`{'\u2588' * BAR_LENGTH}` 100%"
        loading_embed.color = discord.Color.green()
        try:
            await loading_msg.edit(embed=loading_embed)
        except Exception:
            pass

        await loading_msg.edit(embed=pages[0], view=make_view())
        await log_dev_cmd(f"Listed {total} servers" + (f" (filter: {search})" if search else ""))

    elif text.lower().startswith("cat!rainstatus"):
        channel = await Channel.get_or_none(channel_id=message.channel.id)
        if not channel:
            await message.reply("This channel is not setup.")
            return

        if channel.cat_rains <= 0:
            await message.reply("No active rain in this channel.")
            return

        now = datetime.datetime.utcnow()
        if hasattr(channel, "rain_end_time") and channel.rain_end_time:
            remaining = channel.rain_end_time - now
            if remaining.total_seconds() < 0:
                remaining_str = "less than a second"
            else:
                minutes, seconds = divmod(int(remaining.total_seconds()), 60)
                hours, minutes = divmod(minutes, 60)
                remaining_str = f"{hours}h {minutes}m {seconds}s"
        else:
            remaining_str = "Unknown"

        await message.reply(
            f"\U0001f327\ufe0f Rain status:\n"
            f" - Cats remaining: {channel.cat_rains}\n"
            f" - Time left: {remaining_str}"
        )
        logging.info(f"Rain status checked in channel {message.channel.id} by {message.author}")
        await log_dev_cmd(f"Rain status: {channel.cat_rains} cats remaining")

    elif text.lower().startswith("cat!blacklist user "):
        args = text[len("cat!blacklist user "):].strip()
        tokens = args.split(None, 1)

        if len(tokens) < 1 or not tokens[0]:
            await message.reply("Usage: `cat!blacklist user <user_id> [reason]`")
            return

        try:
            user_id = int(tokens[0])
            reason = tokens[1].strip() if len(tokens) > 1 else "No reason provided"
        except ValueError:
            await message.reply(f"Invalid user ID: `{tokens[0]}`")
            return

        success = await add_to_blacklist(user_id, "user", reason, message.author.id)
        if success:
            await message.reply(f"\u2705 User `{user_id}` blacklisted. Reason: {reason}")
            logging.info(f"User {user_id} blacklisted by {message.author}: {reason}")
            await log_dev_cmd(f"Blacklisted user {user_id} \u2014 {reason}")
        else:
            await message.reply(f"User `{user_id}` is already blacklisted.")

    elif text.lower().startswith("cat!blacklist guild "):
        args = text[len("cat!blacklist guild "):].strip()
        tokens = args.split(None, 1)

        if len(tokens) < 1 or not tokens[0]:
            await message.reply("Usage: `cat!blacklist guild <guild_id> [reason]`")
            return

        try:
            guild_id = int(tokens[0])
            reason = tokens[1].strip() if len(tokens) > 1 else "No reason provided"
        except ValueError:
            await message.reply(f"Invalid guild ID: `{tokens[0]}`")
            return

        success = await add_to_blacklist(guild_id, "guild", reason, message.author.id)
        if success:
            await message.reply(f"\u2705 Guild `{guild_id}` blacklisted. Reason: {reason}")
            logging.info(f"Guild {guild_id} blacklisted by {message.author}: {reason}")
            await log_dev_cmd(f"Blacklisted guild {guild_id} \u2014 {reason}")
        else:
            await message.reply(f"Guild `{guild_id}` is already blacklisted.")

    elif text.lower().startswith("cat!blacklist channel "):
        args = text[len("cat!blacklist channel "):].strip()
        tokens = args.split(None, 1)

        if len(tokens) < 1 or not tokens[0]:
            await message.reply("Usage: `cat!blacklist channel <channel_id> [reason]`")
            return

        try:
            channel_id = int(tokens[0])
            reason = tokens[1].strip() if len(tokens) > 1 else "No reason provided"
        except ValueError:
            await message.reply(f"Invalid channel ID: `{tokens[0]}`")
            return

        success = await add_to_blacklist(channel_id, "channel", reason, message.author.id)
        if success:
            await message.reply(f"\u2705 Channel `{channel_id}` blacklisted. Reason: {reason}")
            logging.info(f"Channel {channel_id} blacklisted by {message.author}: {reason}")
            await log_dev_cmd(f"Blacklisted channel {channel_id} \u2014 {reason}")
        else:
            await message.reply(f"Channel `{channel_id}` is already blacklisted.")

    elif text.lower().startswith("cat!unblacklist "):
        args = text[len("cat!unblacklist "):].strip()
        tokens = args.split()

        if len(tokens) < 2:
            await message.reply("Usage: `cat!unblacklist <type> <id>` (type: user/guild/channel)")
            return

        blacklist_type = tokens[0].lower()
        try:
            target_id = int(tokens[1])
        except ValueError:
            await message.reply(f"Invalid ID: `{tokens[1]}`")
            return

        if blacklist_type not in ["user", "guild", "channel"]:
            await message.reply("Invalid type. Use: user, guild, or channel")
            return

        success = await remove_from_blacklist(target_id, blacklist_type)
        if success:
            await message.reply(f"\u2705 `{target_id}` removed from {blacklist_type} blacklist.")
            logging.info(f"{blacklist_type.capitalize()} {target_id} removed from blacklist by {message.author}")
            await log_dev_cmd(f"Removed {blacklist_type} {target_id} from blacklist")
        else:
            await message.reply(f"That {blacklist_type} is not blacklisted.")

    elif text.lower().startswith("cat!blacklist view "):
        args = text[len("cat!blacklist view "):].strip()
        tokens = args.split()

        if len(tokens) < 1:
            await message.reply("Usage: `cat!blacklist view <type>` (type: user/guild/channel)")
            return

        blacklist_type = tokens[0].lower()

        if blacklist_type not in ["user", "guild", "channel"]:
            await message.reply("Invalid type. Use: user, guild, or channel")
            return

        entries = await Blacklist.collect(f"blacklist_type = $1 ORDER BY blacklisted_at DESC", blacklist_type)

        if not entries:
            await message.reply(f"No blacklisted {blacklist_type}s.")
            return

        embed = discord.Embed(
            title=f"Blacklisted {blacklist_type.capitalize()}s ({len(entries)})",
            color=Colors.red,
            description=""
        )

        for entry in entries[:25]:
            try:
                blacklisted_by = await shared.bot.fetch_user(entry.blacklisted_by)
                by_name = blacklisted_by.name
            except Exception:
                by_name = f"ID: {entry.blacklisted_by}"

            timestamp = f"<t:{entry.blacklisted_at}:R>"
            embed.add_field(
                name=f"{entry.target_id}",
                value=f"**Reason:** {entry.reason}\n**By:** {by_name}\n**When:** {timestamp}",
                inline=False
            )

        if len(entries) > 25:
            embed.set_footer(text=f"Showing 25 of {len(entries)} entries")

        await message.reply(embed=embed)

    elif text.lower().startswith("cat!sync"):
        parts = text.split()
        try:
            await message.reply("Syncing commands...")
            if len(parts) > 1 and parts[1] == "guild":
                shared.bot.tree.copy_global_to(guild=message.guild)
                synced = await shared.bot.tree.sync(guild=message.guild)
                await message.reply(f"Guild-synced {len(synced)} commands to **{message.guild.name}**.")
                await log_dev_cmd(f"Guild-synced {len(synced)} commands to {message.guild.name}")
            elif len(parts) > 1 and parts[1] == "clear":
                shared.bot.tree.clear_commands(guild=message.guild)
                await shared.bot.tree.sync(guild=message.guild)
                await message.reply("Cleared guild-specific command overrides.")
                await log_dev_cmd("Cleared guild command overrides")
            else:
                synced = await shared.bot.tree.sync()
                await message.reply(f"Globally synced {len(synced)} commands. (May take up to 1 hour to propagate)")
                await log_dev_cmd(f"Globally synced {len(synced)} commands")
        except Exception:
            await message.reply(f"Sync failed:\n```{traceback.format_exc()}```")

    elif text.lower().startswith("cat!forcespawn"):
        parts = text.split()
        target_channel_id = str(message.channel.id)
        if len(parts) > 1:
            try:
                target_channel_id = str(int(parts[1]))
            except ValueError:
                await message.reply("Usage: `cat!forcespawn [channel_id]`")
                return
        try:
            await spawn_cat(target_channel_id, force_spawn=True)
            await message.reply(f"Forced a cat to spawn in <#{target_channel_id}>.")
            await log_dev_cmd(f"Force-spawned cat in channel {target_channel_id}")
        except Exception:
            await message.reply(f"Spawn failed:\n```{traceback.format_exc()}```")

    elif text.lower().startswith("cat!give "):
        parts = text.split()
        if len(parts) < 3:
            await message.reply("Usage: `cat!give <user_id> <amount>`")
            return
        try:
            target_uid = int(parts[1])
            amount = int(parts[2])
        except ValueError:
            await message.reply("Invalid user ID or amount.")
            return
        try:
            profiles = await Profile.collect("user_id = $1", target_uid)
            if not profiles:
                await message.reply(f"No profile found for `{target_uid}`. They must have used the bot at least once.")
                return
            for p in profiles:
                p.cats = (p.cats or 0) + amount
                await p.save()
            await message.reply(f"Gave **{amount}** cats to `{target_uid}` across {len(profiles)} server(s).")
            logging.info(f"Admin gave {amount} cats to {target_uid} (by {message.author})")
            await log_dev_cmd(f"Gave {amount} cats to {target_uid} across {len(profiles)} servers")
        except Exception:
            await message.reply(f"Failed:\n```{traceback.format_exc()}```")

    elif text.lower().startswith("cat!userinfo "):
        parts = text.split()
        if len(parts) < 2:
            await message.reply("Usage: `cat!userinfo <user_id>`")
            return
        try:
            target_uid = int(parts[1])
        except ValueError:
            await message.reply("Invalid user ID.")
            return
        try:
            profiles = await Profile.collect("user_id = $1", target_uid)
            user_global = await User.get_or_none(user_id=target_uid)
            bl_info = await get_blacklist_info(target_uid, "user")
            try:
                discord_user = await shared.bot.fetch_user(target_uid)
                username = f"{discord_user} ({discord_user.id})"
            except Exception:
                username = f"Unknown ({target_uid})"
            embed = discord.Embed(title=f"User Info: {username}", color=Colors.brown)
            embed.add_field(name="Profiles (servers)", value=str(len(profiles)), inline=True)
            if profiles:
                total_cats = sum(p.cats or 0 for p in profiles)
                embed.add_field(name="Total Cats (all servers)", value=str(total_cats), inline=True)
            if user_global:
                embed.add_field(name="Rain Minutes", value=str(user_global.rain_minutes or 0), inline=True)
                embed.add_field(name="Premium", value="Yes" if user_global.premium else "No", inline=True)
                embed.add_field(name="Custom Cat", value=user_global.custom or "None", inline=True)
            if bl_info:
                embed.add_field(name="BLACKLISTED", value=f"Reason: {bl_info.get('reason', 'N/A')}", inline=False)
            await message.reply(embed=embed)
        except Exception:
            await message.reply(f"Failed:\n```{traceback.format_exc()}```")

    elif text.lower().startswith("cat!announce "):
        announcement = text[len("cat!announce "):].strip()
        if not announcement:
            await message.reply("Usage: `cat!announce <message>`")
            return
        sent = 0
        failed = 0
        await message.reply("Sending announcement to all channels...")
        async for ch_record in Channel.all():
            try:
                partial = shared.bot.get_partial_messageable(int(ch_record.channel_id))
                await partial.send(f"**Announcement:** {announcement}")
                sent += 1
            except Exception:
                failed += 1
        await message.reply(f"Announced to **{sent}** channels ({failed} failed).")
        logging.info(f"Announcement sent to {sent} channels by {message.author}: {announcement[:100]}")


async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    msg = str(error.original) if isinstance(error, discord.app_commands.CommandInvokeError) else str(error)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

    try:
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        tb_str = "".join(tb)[-1000:]
        guild_str = f"{interaction.guild.name} ({interaction.guild.id})" if interaction.guild else "DM"
        embed = discord.Embed(
            title="\u26a0\ufe0f Command Error",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Command", value=f"`/{interaction.command.name}`" if interaction.command else "Unknown", inline=True)
        embed.add_field(name="User", value=f"{interaction.user} ({interaction.user.id})", inline=True)
        embed.add_field(name="Server", value=guild_str, inline=False)
        embed.add_field(name="Error", value=f"```{msg[:500]}```", inline=False)
        embed.add_field(name="Traceback", value=f"```py\n{tb_str}\n```", inline=False)
        await log_error(embed)
    except Exception as log_err:
        logging.warning(f"Error log failed: {log_err}")


async def on_app_command_completion(interaction: discord.Interaction, command: discord.app_commands.Command = None):
    global total_commands_used
    total_commands_used += 1
    if command is None:
        command = interaction.command
    try:
        guild_str = f"{interaction.guild.name} ({interaction.guild.id})" if interaction.guild else "DM"
        channel_str = (
            f"#{interaction.channel.name} ({interaction.channel.id})"
            if hasattr(interaction.channel, "name")
            else str(interaction.channel_id)
        )
        options_str = ""
        if interaction.data and interaction.data.get("options"):
            def _flatten_options(opts: list, prefix: str = "") -> list[str]:
                parts = []
                for opt in opts:
                    opt_type = opt.get("type", 0)
                    if opt_type in (1, 2):
                        sub_prefix = (prefix + " " if prefix else "") + opt["name"]
                        parts.extend(_flatten_options(opt.get("options", []), sub_prefix))
                    else:
                        name = (prefix + " " if prefix else "") + opt["name"]
                        parts.append(f"{name}: {opt.get('value', '?')}")
                return parts
            flat = _flatten_options(interaction.data["options"])
            options_str = ", ".join(flat)

        embed = discord.Embed(
            title=f"\U0001f527 /{command.name}",
            color=Colors.brown,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="User", value=f"{interaction.user} ({interaction.user.id})", inline=True)
        embed.add_field(name="Server", value=guild_str, inline=True)
        embed.add_field(name="Channel", value=channel_str, inline=False)
        if options_str:
            embed.add_field(name="Options", value=options_str[:1000], inline=False)
        embed.set_footer(text=f"Total Commands: {total_commands_used} \u2022 Total Servers: {len(shared.bot.guilds)}")
        await log_command(embed)
    except Exception as e:
        logging.warning(f"Command log failed: {e}")


@shared.bot.event
async def on_message(message: discord.Message):
    global emojis, last_loop_time
    text = message.content
    if not shared.bot.user or message.author.id == shared.bot.user.id:
        return

    if await check_message_blacklist(message):
        return

    await on_message_dev_commands(message)

    if time.time() > last_loop_time + 300:
        last_loop_time = time.time()
        shared.bot.loop.create_task(background_loop())

    if message.guild is None:
        try:
            if text.startswith("disable"):
                try:
                    where = text.split(" ")[1]
                    user = await Profile.get_or_create(guild_id=int(where), user_id=message.author.id)
                    user.reminders_enabled = False
                    await user.save()
                    await message.channel.send("reminders disabled")
                except Exception:
                    await message.channel.send("failed. check if your guild id is correct")
                    return
            elif text == "lol_i_have_dmed_the_cat_bot_and_got_an_ach":
                await message.channel.send('which part of "send in server" was unclear?')
            else:
                await message.channel.send('good job! please send "lol_i_have_dmed_the_cat_bot_and_got_an_ach" in server to get your ach!')
        except Exception:
            pass
        return

    server = await Server.get_or_create(server_id=message.guild.id)
    server = await Server.get_or_create(server_id=message.guild.id)

    achs = [
        ["cat?", "startswith", "???"],
        ["catn", "exact", "catn"],
        ["cat!coupon jr0f-pzka", "exact", "coupon_user"],
        ["pineapple", "exact", "pineapple"],
        ["cat!i_like_cat_website", "exact", "website_user"],
        ["cat!i_clicked_there", "exact", "click_here"],
        ["cat!lia_is_cute", "exact", "nerd"],
        ["i read help", "exact", "patient_reader"],
        [str(shared.bot.user.id), "in", "who_ping"],
        ["lol_i_have_dmed_the_cat_bot_and_got_an_ach", "exact", "dm"],
        ["dog", "exact", "not_quite"],
        ["egril", "exact", "egril"],
        ["-.-. .- -", "exact", "morse_cat"],
        ["tac", "exact", "reverse"],
        ["cat!n4lltvuCOKe2iuDCmc6JsU7Jmg4vmFBj8G8l5xvoDHmCoIJMcxkeXZObR6HbIV6", "veryexact", "dataminer"],
        ["meow", "silly", "meow"]
    ]

    reactions = [
        ["v1;", "custom", "why_v1"],
        ["proglet", "custom", "professor_cat"],
        ["xnopyt", "custom", "vanish"],
        ["silly", "custom", "sillycat"],
        ["indev", "vanilla", "\U0001f438"],
        ["bleh", "custom", "blepcat"],
        ["blep", "custom", "blepcat"],
    ]

    responses = [
        [
            "cellua good",
            "in",
            ".".join([str(random.randint(2, 254)) for _ in range(4)]),
        ],
        [
            "https://tenor.com/view/this-cat-i-have-hired-this-cat-to-stare-at-you-hired-cat-cat-stare-gif-26392360",
            "exact",
            "https://tenor.com/view/cat-staring-cat-gif-16983064494644320763",
        ],
    ]

    if config.RAIN_CHANNEL_ID and message.author.id not in OWNER_IDS and message.channel.id == config.RAIN_CHANNEL_ID and text.lower().startswith("cat!rain"):
        arguements = text.split(" ")

        if len(arguements) < 3:
            await message.reply("Usage: `cat!rain <user_id> short/medium/long/N` or `cat!rain give <user_id> <amount>`")
            return

        if arguements[1].lower() == "give":
            if len(arguements) < 4:
                await message.reply("Usage: `cat!rain give <user_id> <amount>`")
                return
            try:
                uid = int(arguements[2])
                amount = int(arguements[3])
            except ValueError:
                await message.reply("Invalid user ID or amount.")
                return
            if amount <= 0:
                await message.reply("Amount must be > 0.")
                return
            try:
                user = await User.get_or_create(user_id=uid)
                if not user.rain_minutes:
                    user.rain_minutes = 0
                old_minutes = user.rain_minutes
                user.rain_minutes += amount
                user.premium = True
                await user.save()

                try:
                    duser = await shared.bot.fetch_user(uid)
                    uname = str(duser)
                except Exception:
                    uname = f"ID {uid}"

                await message.reply(f"Gave **{amount}** rain minutes to **{uname}** (now has **{user.rain_minutes}**).")

                try:
                    person = await fetch_dm_channel(user)
                    await person.send(
                        f"**You have recieved {amount} minutes of Cat Rain!** \u2614\n\nThanks for your support!\nYou can start a rain with `/rain`. By buying you also get access to `/editprofile` and `/customcat` commands as well as a role in [our Discord server](<https://discord.gg/BbDXVm4YTg>)!\n\nEnjoy your goods!"
                    )
                except Exception:
                    pass

                try:
                    rain_embed = discord.Embed(
                        title="\u2614 Rain Minutes Added",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow(),
                    )
                    rain_embed.add_field(name="User", value=f"{uname} ({uid})", inline=True)
                    rain_embed.add_field(name="Minutes Added", value=str(amount), inline=True)
                    rain_embed.add_field(name="Total Rain Minutes", value=str(user.rain_minutes), inline=True)
                    rain_embed.add_field(name="Added By", value=f"{message.author} ({message.author.id})", inline=False)
                    rain_embed.set_footer(text=f"Total Servers: {len(shared.bot.guilds)}")
                    await log_rain(rain_embed)
                except Exception as log_err:
                    logging.warning(f"Rain add log failed: {log_err}")
            except Exception:
                await message.reply(f"Failed:\n```{traceback.format_exc()}```")
            return

        if arguements[1].lower() == "remove":
            if len(arguements) < 4:
                await message.reply("Usage: `cat!rain remove <user_id> <amount>`")
                return
            try:
                uid = int(arguements[2])
                amount = int(arguements[3])
            except ValueError:
                await message.reply("Invalid user ID or amount.")
                return
            if amount <= 0:
                await message.reply("Amount must be > 0.")
                return
            try:
                user = await User.get_or_create(user_id=uid)
                if not user.rain_minutes:
                    user.rain_minutes = 0
                old_minutes = user.rain_minutes
                user.rain_minutes = max(0, user.rain_minutes - amount)
                await user.save()

                try:
                    duser = await shared.bot.fetch_user(uid)
                    uname = str(duser)
                except Exception:
                    uname = f"ID {uid}"

                await message.reply(f"Removed **{amount}** rain minutes from **{uname}** (was {old_minutes}, now has **{user.rain_minutes}**).")
            except Exception:
                await message.reply(f"Failed:\n```{traceback.format_exc()}```")
            return

        try:
            uid = int(arguements[1])
            rain_duration = arguements[2]
        except (ValueError, IndexError):
            await message.reply("Usage: `cat!rain <user_id> short/medium/long/N` or `cat!rain give <user_id> <amount>`")
            return

        try:
            user = await User.get_or_create(user_id=uid)
            if not user.rain_minutes:
                user.rain_minutes = 0

            if rain_duration == "short":
                user.rain_minutes += 2
                minutes_added = 2
            elif rain_duration == "medium":
                user.rain_minutes += 10
                minutes_added = 10
            elif rain_duration == "long":
                user.rain_minutes += 20
                minutes_added = 20
            else:
                try:
                    minutes_added = int(rain_duration)
                except ValueError:
                    await message.reply("Invalid duration. Use `short`, `medium`, `long`, or a number.")
                    return
                user.rain_minutes += minutes_added
                user.rain_minutes_bought += minutes_added
            user.premium = True
            await user.save()

            await message.reply(f"Gave **{minutes_added}** rain minutes to <@{uid}> (now has **{user.rain_minutes}**).")

            try:
                person = await fetch_dm_channel(user)
                await person.send(
                    f"**You have recieved {minutes_added} minutes of Cat Rain!** \u2614\n\nThanks for your support!\nYou can start a rain with `/rain`. By buying you also get access to `/editprofile` and `/customcat` commands as well as a role in [our Discord server](<https://discord.gg/BbDXVm4YTg>)!\n\nEnjoy your goods!"
                )
            except Exception:
                pass

            try:
                rain_embed = discord.Embed(
                    title="\u2614 Rain Minutes Added",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow(),
                )
                rain_embed.add_field(name="User ID", value=str(user.user_id), inline=True)
                rain_embed.add_field(name="Minutes Added", value=str(minutes_added), inline=True)
                rain_embed.add_field(name="Total Rain Minutes", value=str(user.rain_minutes), inline=True)
                rain_embed.add_field(name="Added By", value=f"{message.author} ({message.author.id})", inline=False)
                rain_embed.set_footer(text=f"Total Servers: {len(shared.bot.guilds)}")
                await log_rain(rain_embed)
            except Exception as log_err:
                logging.warning(f"Rain add log failed: {log_err}")
        except Exception:
            await message.reply(f"Failed:\n```{traceback.format_exc()}```")

        return

    react_count = 0

    if " " not in text and len(text) > 7 and text.isalnum():
        s = text.lower()
        total_vow = 0
        total_illegal = 0
        for i in "aeuio":
            total_vow += s.count(i)
        illegal = [
            "bk", "fq", "jc", "jt", "mj", "qh", "qx", "vj", "wz", "zh",
            "bq", "fv", "jd", "jv", "mq", "qj", "qy", "vk", "xb", "zj",
            "bx", "fx", "jf", "jw", "mx", "qk", "qz", "vm", "xg", "zn",
            "cb", "fz", "jg", "jx", "mz", "ql", "sx", "vn", "xj", "zq",
            "cf", "gq", "jh", "jy", "pq", "qm", "sz", "vp", "xk", "zr",
            "cg", "gv", "jk", "jz", "pv", "qn", "tq", "vq", "xv", "zs",
            "cj", "gx", "jl", "kq", "px", "qo", "tx", "vt", "xz", "zx",
            "cp", "hk", "jm", "kv", "qb", "qp", "vb", "vw", "yq",
            "cv", "hv", "jn", "kx", "qc", "qr", "vc", "vx", "yv",
            "cw", "hx", "jp", "kz", "qd", "qs", "vd", "vz", "yz",
            "cx", "hz", "jq", "lq", "qe", "qt", "vf", "wq", "zb",
            "dx", "iy", "jr", "lx", "qf", "qv", "vg", "wv", "zc",
            "fk", "jb", "js", "mg", "qg", "qw", "vh", "wx", "zg",
        ]
        for j in illegal:
            if j in s:
                total_illegal += 1
        vow_perc = 0
        const_perc = len(text)
        if total_vow != 0:
            vow_perc = len(text) / total_vow
        if total_vow != len(text):
            const_perc = len(text) / (len(text) - total_vow)
        if (vow_perc <= 3 and const_perc >= 6) or total_illegal >= 2:
            try:
                if reactions_ratelimit.get(message.guild.id, 0) < 100:
                    if server.do_reactions:
                        await message.add_reaction(get_emoji("staring_cat"))
                    react_count += 1
                    reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
                    logging.debug("Reaction added: %s", "staring_cat")
            except Exception:
                pass

    try:
        if "robotop" in message.author.name.lower() and "i rate **cat" in message.content.lower():
            icon = str(get_emoji("no_ach"))
            await message.reply("**RoboTop**, I rate **you** 0 cats " + icon * 5)

        if "leafbot" in message.author.name.lower() and "hmm... i would rate cat" in message.content.lower():
            icon = str(get_emoji("no_ach")) + " "
            await message.reply("Hmm... I would rate you **0 cats**! " + icon * 5)
    except Exception:
        pass

    if message.author.bot or message.webhook_id is not None:
        return

    for achievement in achs:
        match_text, match_method, achievement_name = achievement
        text_lowered = text.lower()
        if any(
            [
                match_method == "startswith" and text_lowered.startswith(match_text),
                match_method == "re" and re.search(match_text, text_lowered),
                match_method == "exact" and match_text == text_lowered,
                match_method == "veryexact" and match_text == text,
                match_method == "in" and match_text in text_lowered,
            ]
        ):
            await achemb(message, achievement_name, "reply")

    if unidecode.unidecode(text).lower().strip() in [
        "mace", "katu", "kot", "koshka", "macka", "gat", "gata", "kocka",
        "kat", "poes", "kass", "kissa", "chat", "chatte", "gato", "katze",
        "gata", "macska", "kottur", "gatto", "getta", "kakis", "kate",
        "qattus", "qattusa", "katt", "kit", "kishka", "cath", "qitta",
        "katu", "pisik", "biral", "kyaung", "mao", "pusa", "kata",
        "billi", "kucing", "neko", "bekku", "mysyq", "chhma", "goyangi",
        "pucha", "manjar", "muur", "biralo", "gorbeh", "punai", "pilli",
        "kedi", "mushuk", "meo", "demat", "nwamba", "jangwe", "adure",
        "katsi", "bisad,", "paka", "ikati", "ologbo", "wesa", "popoki",
        "piqtuq", "negeru", "poti", "mosi", "michi", "pusi", "oratii",
    ]:
        await achemb(message, "multilingual", "reply")

    for reaction in reactions:
        reaction_prompt, reaction_type, reaction_name = reaction
        if reaction_prompt in text.lower() and reactions_ratelimit.get(message.guild.id, 0) < 100:
            if reaction_type == "custom":
                resolved_emoji = get_emoji(reaction_name)
            elif reaction_type == "vanilla":
                resolved_emoji = reaction_name

            try:
                if server.do_reactions:
                    await message.add_reaction(resolved_emoji)
                react_count += 1
                reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
                logging.debug("Reaction added: %s", reaction_name)
            except Exception:
                pass

    for response in responses:
        match_method, match_text, response_reply = response
        text_lowered = text.lower()
        if any(
            [
                match_method == "startswith" and text_lowered.startswith(match_text),
                match_method == "re" and re.search(match_text, text_lowered),
                match_method == "exact" and match_text == text_lowered,
                match_method == "in" and match_text in text_lowered,
            ]
        ):
            try:
                await message.reply(response_reply)
            except Exception:
                pass
            logging.debug("Response sent: %s", response_reply)

    try:
        if message.author in message.mentions and message.type != discord.MessageType.poll_result and reactions_ratelimit.get(message.guild.id, 0) < 100:
            if server.do_reactions:
                await message.add_reaction(get_emoji("staring_cat"))
            react_count += 1
            reactions_ratelimit[message.guild.id] = reactions_ratelimit.get(message.guild.id, 0) + 1
            logging.debug("Reaction added: %s", "staring_cat")
    except Exception:
        pass

    if react_count >= 3:
        await achemb(message, "silly", "reply")

    if (":place_of_worship:" in text or "\U0001f6d0" in text) and (":cat:" in text or ":staring_cat:" in text or "\U0001f431" in text):
        await achemb(message, "worship", "reply")

    if text.lower() in ["testing testing 1 2 3", "cat!ach"]:
        try:
            await message.reply("test success")
        except Exception:
            pass
        logging.debug("Response sent: %s", "test success")
        await achemb(message, "test_ach", "reply")

    if text.lower() == "please do the cat":
        thing = discord.File("images/socialcredit.jpg", filename="socialcredit.jpg")
        try:
            await message.reply(file=thing)
        except Exception:
            pass
        await achemb(message, "pleasedothecat", "reply")
        logging.debug("Response sent: %s", "please do the cat")

    if text.lower() == "car":
        file = discord.File("images/car.png", filename="car.png")
        embed = discord.Embed(title="car!", color=Colors.brown).set_image(url="attachment://car.png")
        try:
            await message.reply(file=file, embed=embed)
        except Exception:
            pass
        await achemb(message, "car", "reply")
        logging.debug("Response sent: %s", "car")

    if text.lower() == "cart":
        file = discord.File("images/cart.png", filename="cart.png")
        embed = discord.Embed(title="cart!", color=Colors.brown).set_image(url="attachment://cart.png")
        try:
            await message.reply(file=file, embed=embed)
        except Exception:
            pass
        logging.debug("Response sent: %s", "cart")

    try:
        if (
            ("sus" in text.lower() or "amog" in text.lower() or "among" in text.lower() or "impost" in text.lower() or "report" in text.lower())
            and (channel := await Channel.get_or_none(channel_id=message.channel.id))
            and channel.cattype == "Sus"
        ):
            await achemb(message, "sussy", "reply")
    except Exception:
        pass

    if text.lower() == "cat":
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.author.id)
        channel = await Channel.get_or_none(channel_id=message.channel.id)
        if not channel or not channel.cat or channel.cat in temp_catches_storage or user.timeout > time.time():
            if channel and channel.cat_rains == 0 and pointlaugh_ratelimit.get(message.channel.id, 0) < 10:
                try:
                    if server.do_reactions:
                        await message.add_reaction(get_emoji("pointlaugh"))
                    pointlaugh_ratelimit[message.channel.id] = pointlaugh_ratelimit.get(message.channel.id, 0) + 1
                except Exception:
                    pass

            if message.channel.id in temp_belated_storage:
                current_time = message.created_at.timestamp()
                belated = temp_belated_storage[message.channel.id]
                if (
                    channel
                    and "users" in belated
                    and "time" in belated
                    and belated.get("timestamp", 0) + 3 > current_time
                    and message.author.id not in belated["users"]
                ):
                    belated["users"].append(message.author.id)
                    temp_belated_storage[message.channel.id] = belated
                    await progress(message, user, "3cats", True)
                    if channel.cattype == "Fine":
                        await progress(message, user, "2fine", True)
                    if channel.cattype == "Good":
                        await progress(message, user, "good", True)
                    if belated.get("time", 10) + current_time - belated.get("timestamp", 0) < 10:
                        await progress(message, user, "under10", True)
                    if random.randint(0, 1) == 0:
                        await progress(message, user, "even", True)
                    else:
                        await progress(message, user, "odd", True)
                    if channel.cattype and channel.cattype not in ["Fine", "Nice", "Good"]:
                        await progress(message, user, "rare+", True)
                    if user.catnip_active >= time.time() or user.hibernation:
                        await bounty(message, user, channel.cattype)
                    total_count = await Prism.count("guild_id = $1", message.guild.id)
                    user_count = await Prism.count("guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
                    global_boost = 0.06 * math.log(2 * total_count + 1)
                    prism_boost = global_boost + 0.03 * math.log(2 * user_count + 1)
                    if prism_boost > random.random():
                        await progress(message, user, "prism", True)
                    if user.catch_quest == "finenice":
                        if channel.cattype == "Fine" and user.catch_progress in [0, 2]:
                            await progress(message, user, "finenice", True)
                        elif channel.cattype == "Nice" and user.catch_progress in [0, 1]:
                            await progress(message, user, "finenice", True)
                            await progress(message, user, "finenice", True)
        else:
            pls_remove_me_later_k_thanks = channel.cat
            temp_catches_storage.append(channel.cat)
            decided_time = random.uniform(channel.spawn_times_min, channel.spawn_times_max)

            cat_rain_end = False
            if channel.cat_rains > 0:
                channel.cat_rains -= 1
                if channel.cat_rains == 0:
                    cat_rain_end = True
                else:
                    decided_time = random.uniform(1, 2)
                    channel.rain_should_end = int(time.time() + decided_time)

            if channel.yet_to_spawn < time.time():
                channel.yet_to_spawn = time.time() + decided_time + 10
            else:
                channel.yet_to_spawn = 0
                decided_time = 0
            force_rain_summary = None

            try:
                current_time = message.created_at.timestamp()
                channel.lastcatches = current_time
                cat_temp = channel.cat
                channel.cat = 0
                try:
                    if channel.cattype != "":
                        catchtime = discord.utils.snowflake_time(cat_temp)
                        le_emoji = channel.cattype
                    else:
                        var = await message.channel.fetch_message(cat_temp)
                        catchtime = var.created_at
                        catchcontents = var.content

                        partial_type = None
                        for v in allowedemojis:
                            if v in catchcontents:
                                partial_type = v
                                break

                        if not partial_type and "thetrashcellcat" in catchcontents:
                            partial_type = "trashcat"
                            le_emoji = "Trash"
                        else:
                            if not partial_type:
                                return

                            for i in cattypes:
                                if i.lower() in partial_type:
                                    le_emoji = i
                                    break
                except Exception:
                    try:
                        await message.channel.send(f"oopsie poopsie i cant access the original message but {message.author.mention} *did* catch a cat rn")
                    except Exception:
                        pass
                    return

                send_target = message.channel
                try:
                    then = catchtime.timestamp()
                    time_caught = round(abs(current_time - then), 3)
                    if time_caught >= 1:
                        time_caught = round(time_caught, 2)

                    days, time_left = divmod(time_caught, 86400)
                    hours, time_left = divmod(time_left, 3600)
                    minutes, seconds = divmod(time_left, 60)

                    caught_time = ""
                    if days:
                        caught_time = caught_time + str(int(days)) + " days "
                    if hours:
                        caught_time = caught_time + str(int(hours)) + " hours "
                    if minutes:
                        caught_time = caught_time + str(int(minutes)) + " minutes "
                    if seconds:
                        pre_time = round(seconds, 3)
                        if pre_time % 1 == 0:
                            pre_time = str(int(pre_time)) + ".00"
                        caught_time = caught_time + str(pre_time) + " seconds "
                    do_time = True
                    if not caught_time:
                        caught_time = "0.000 seconds (woah) "
                    if time_caught <= 0:
                        do_time = False
                except Exception:
                    do_time = False
                    caught_time = "undefined amounts of time "

                try:
                    if time_caught >= 0:
                        temp_belated_storage[message.channel.id] = {"time": time_caught, "users": [message.author.id], "timestamp": current_time}
                except Exception:
                    pass

                if channel.cat_rains > 0 or cat_rain_end:
                    do_time = False

                suffix_string = ""
                silly_amount = 1

                double_chance = 0
                triple_chance = 0
                single_chance = 100
                none_chance = 0
                double_boost_chance = 0
                rain_chance = 0
                purr_all_triple = False
                packs = []
                double_boost = False
                double_first = 0
                timer_add_chance = 0
                packs_gained = []

                if user.perks:
                    if user.catnip_active < time.time():
                        if not user.catnip_active:
                            user.catnip_active = False
                            suffix_string += f"\n{get_emoji('catnip_disabled')} Your catnip expired! Run /catnip to get more."
                        perks = []
                    else:
                        perks = user.perks
                    perks_info = catnip_list["perks"]

                    if len(perks) > 0:
                        logging.debug("Catnip active with %d perks", len(perks))

                    for perk in perks:
                        h = perk.split("_")
                        rarity = int(h[0])
                        type = int(h[1])
                        id = perks_info[type - 1]["id"]

                        if id == "double":
                            double_chance += perks_info[0]["values"][rarity]
                            single_chance -= perks_info[0]["values"][rarity]
                        elif id == "triple_none":
                            triple_chance += perks_info[1]["values"][rarity]
                            none_chance += perks_info[1]["values"][rarity] / 2
                            single_chance -= perks_info[1]["values"][rarity] * (1.5)
                        elif "pack" in id:
                            for num, pack in enumerate(pack_data):
                                if pack["name"].lower() in id:
                                    packs.append((num, perks_info[type - 1]["values"][rarity]))
                                    break
                        elif id == "double_boost":
                            double_boost_chance += perks_info[8]["values"][rarity]
                        elif id == "triple_ach":
                            purr_all_triple = True
                        elif id == "timer_add":
                            timer_add_chance += perks_info[10]["values"][rarity]
                        elif id == "rain_boost":
                            rain_chance += perks_info[12]["values"][rarity]
                        elif id == "double_first":
                            double_first += perks_info[13]["values"][rarity]

                    for i in packs:
                        chance = random.random() * 100
                        if chance <= i[1]:
                            _pn = pack_data[i[0]]["name"]
                            packs_gained.append(_pn)
                            user[f"pack_{_pn.lower()}"] += 1
                            suffix_string += f"\n{get_emoji(_pn.lower() + 'pack')} You got a {_pn} pack! You now have {user[f'pack_{_pn.lower()}']:,} packs of this type!"

                    chance = random.random() * 100
                    if chance <= double_boost_chance:
                        double_boost = True

                    chance = random.random() * 100
                    if chance <= timer_add_chance:
                        user.catnip_active += 300
                        suffix_string += f"\n\u23f0 You got +5 minutes on your catnip timer! It will now expire <t:{user.catnip_active}:R>"

                    if double_first > user.catnip_total_cats:
                        user.catnip_total_cats += 1
                        double_chance = 100 - triple_chance
                        single_chance = 0
                        none_chance = 0

                    if time_caught > 0 and time_caught == int(time_caught):
                        user.perfection_count += 1
                        if purr_all_triple:
                            triple_chance = 100
                            double_chance = 0
                            single_chance = 0
                            none_chance = 0

                    if "undefined" not in caught_time and time_caught > 0:
                        raw_digits = "".join(char for char in caught_time[:-1] if char.isdigit())
                        if len(set(raw_digits)) == 1 and purr_all_triple:
                            triple_chance = 100
                            double_chance = 0
                            single_chance = 0
                            none_chance = 0

                    if single_chance < 0:
                        single_chance = 0
                        double_chance = 100 - triple_chance - none_chance
                    if double_chance < 0:
                        double_chance = 0
                        if 100 - triple_chance < 25:
                            none_chance = 25
                            triple_chance = 75
                    if none_chance < 0:
                        none_chance = 0

                    if random.random() * 100 < rain_chance:
                        if channel.cat_rains == 0:
                            force_rain_summary = config.cat_cought_rain.get(channel.channel_id, {}).copy()
                            channel.cat_rains = 10
                            decided_time = random.uniform(1, 2)
                            channel.rain_should_end = int(time.time() + decided_time)
                            channel.yet_to_spawn = 0
                            config.cat_cought_rain[channel.channel_id] = {}
                            config.rain_starter[channel.channel_id] = message.author.id
                            shared.bot.loop.create_task(rain_recovery_loop(channel))
                            suffix_string += "\n\u2614 Catnip started a short rain! 10 cats will spawn."

                    chance = random.random() * 100
                    if chance <= triple_chance:
                        silly_amount *= 3
                        suffix_string += f"\n{get_emoji('catnip')} catnip worked! your cat was TRIPLED by catnip!1!!1!"
                        user.catnip_activations += 2
                    elif chance <= triple_chance + double_chance:
                        silly_amount *= 2
                        suffix_string += f"\n{get_emoji('catnip')} catnip worked! your cat was doubled by catnip!!1!"
                        user.catnip_activations += 1
                    elif chance <= triple_chance + double_chance + single_chance:
                        silly_amount *= 1
                    elif chance <= triple_chance + double_chance + single_chance + none_chance:
                        silly_amount *= 0
                        suffix_string += "\n\U0001f6ab catnip failed! your cat was uncought. tragic."

                total_rain = await User.sum(
                    "total_rain_minutes",
                    "blessings_enabled = true"
                )

                bless_chance = total_rain * 0.0001
                if bless_chance > random.random():
                    blesser_l = await User.collect("blessings_enabled = true AND rain_minutes_bought > 0 ORDER BY -ln(random()) / rain_minutes_bought LIMIT 1")

                    if blesser_l:
                        if silly_amount == 0:
                            silly_amount += 1
                        else:
                            silly_amount *= 2

                        blesser = blesser_l[0]
                        blesser.cats_blessed += 1
                        if not blesser.username:
                            blesser.username = (await shared.bot.fetch_user(blesser.user_id)).name
                        asyncio.create_task(blesser.save())

                        logging.debug("Catch blessed")

                        if blesser.blessings_anonymous:
                            blesser_text = "\U0001f4ab Anonymous Supporter"
                        else:
                            blesser_text = f"{blesser.emoji or '\U0001f4ab'} {blesser.username}"

                        if silly_amount > 1:
                            suffix_string += f"\n{blesser_text} blessed your catch and it got doubled!"
                        else:
                            suffix_string += f"\n{blesser_text} blessed your catch and it got saved!"

                total_prisms = await Prism.collect("guild_id = $1", message.guild.id)
                user_prisms = await Prism.collect("guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
                global_boost = 0.06 * math.log(2 * len(total_prisms) + 1)
                user_boost = global_boost + 0.03 * math.log(2 * len(user_prisms) + 1)
                did_boost = False
                if user_boost > random.random():
                    if random.uniform(0, user_boost) > global_boost:
                        prism_which_boosted = random.choice(user_prisms)
                    else:
                        prism_which_boosted = random.choice(total_prisms)

                    if prism_which_boosted.user_id == message.author.id:
                        boost_applied_prism = "Your prism " + prism_which_boosted.name
                    else:
                        boost_applied_prism = f"<@{prism_which_boosted.user_id}>'s prism " + prism_which_boosted.name

                    did_boost = True
                    user.boosted_catches += 1
                    prism_which_boosted.catches_boosted += 1
                    asyncio.create_task(prism_which_boosted.save())
                    logging.debug("Boosted from %s", le_emoji)
                    idx_shift = 0
                    try:
                        le_old_emoji = le_emoji
                        if double_boost:
                            idx_shift = cattypes.index(le_emoji) + 2
                        else:
                            idx_shift = cattypes.index(le_emoji) + 1
                        le_emoji = cattypes[idx_shift]
                        normal_bump = True
                    except IndexError:
                        normal_bump = False
                        if not channel.forcespawned:
                            if idx_shift == len(cattypes) + 1:
                                rainboost = 1200
                            elif idx_shift == len(cattypes):
                                rainboost = 600
                            logging.debug("Boosted to rain: %d", rainboost)
                            channel.cat_rains += math.ceil(rainboost / 2.75)
                            if channel.cat_rains > math.ceil(rainboost / 2.75):
                                await message.channel.send(f"# \u203c\ufe0f\u203c\ufe0f RAIN EXTENDED BY {int(rainboost / 60)} MINUTES \u203c\ufe0f\u203c\ufe0f")
                                await message.channel.send(f"# \u203c\ufe0f\u203c\ufe0f RAIN EXTENDED BY {int(rainboost / 60)} MINUTES \u203c\ufe0f\u203c\ufe0f")
                                await message.channel.send(f"# \u203c\ufe0f\u203c\ufe0f RAIN EXTENDED BY {int(rainboost / 60)} MINUTES \u203c\ufe0f\u203c\ufe0f")
                            else:
                                force_rain_summary = config.cat_cought_rain.get(channel.channel_id, {}).copy()
                                decided_time = random.uniform(1, 2)
                                channel.rain_should_end = int(time.time() + decided_time)
                                channel.yet_to_spawn = 0
                                config.cat_cought_rain[channel.channel_id] = {}
                                config.rain_starter[channel.channel_id] = message.author.id
                                shared.bot.loop.create_task(rain_recovery_loop(channel))

                    if normal_bump:
                        if double_boost:
                            suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} boosted this catch twice from a {get_emoji(le_old_emoji.lower() + 'cat')} {le_old_emoji} cat to a {get_emoji(le_emoji.lower() + 'cat')} {le_emoji} cat!"
                        else:
                            suffix_string += f"\n{get_emoji('prism')} {boost_applied_prism} boosted this catch from a {get_emoji(le_old_emoji.lower() + 'cat')} {le_old_emoji} cat!"
                    elif not channel.forcespawned:
                        suffix_string += (
                            f"\n{get_emoji('prism')} {boost_applied_prism} tried to boost this catch, but failed! A {rainboost // 60}m rain will start!"
                        )

                icon = get_emoji(le_emoji.lower() + "cat")

                if channel.channel_id in config.cat_cought_rain:
                    if le_emoji not in config.cat_cought_rain[channel.channel_id]:
                        config.cat_cought_rain[channel.channel_id][le_emoji] = []
                    for _ in range(silly_amount):
                        config.cat_cought_rain[channel.channel_id][le_emoji].append(f"<@{user.user_id}>")
                    for i in packs_gained:
                        if i not in config.cat_cought_rain[channel.channel_id]:
                            config.cat_cought_rain[channel.channel_id][i] = []
                        config.cat_cought_rain[channel.channel_id][i].append(f"<@{user.user_id}>")

                if random.randint(0, 7) == 0:
                    suffix_string += f"\n\u2614 Try </rain:{RAIN_ID}> to start a cat rain!"
                if random.randint(0, 19) == 0:
                    suffix_string += "\n\U0001f4a1 " + random.choice(hints)

                custom_cough_strings = {
                    "Corrupt": "{username} coought{type} c{emoji}at!!!!404!\nYou now BEEP {count} cats of dCORRUPTED!!\nthis fella wa- {time}!!!!",
                    "eGirl": "{username} cowought {emoji} {type} cat~~ ^^\nYou-u now *blushes* hawe {count} cats of dat tywe~!!!\nthis fella was <3 cought in {time}!!!!",
                    "Rickroll": "{username} cought {emoji} {type} cat!!!!1!\nYou will never give up {count} cats of dat type!!!\nYou wouldn't let them down even after {time}!!!!",
                    "Sus": "{username} cought {emoji} {type} cat!!!!1!\nYou have vented infront of {count} cats of dat type!!!\nthis sussy baka was cought in {time}!!!!",
                    "Professor": "{username} caught {emoji} {type} cat!\nThou now hast {count} cats of that type!\nThis fellow was caught 'i {time}!",
                    "8bit": "{username} c0ught {emoji} {type} cat!!!!1!\nY0u n0w h0ve {count} cats 0f dat type!!!\nth1s fe11a was c0ught 1n {time}!!!!",
                    "Reverse": "!!!!{time} in cought was fella this\n!!!type dat of cats {count} have now You\n!1!!!!cat {type} {emoji} cought {username}",
                }

                if channel.cought:
                    coughstring = channel.cought
                elif le_emoji in custom_cough_strings:
                    coughstring = custom_cough_strings[le_emoji]
                else:
                    coughstring = "{username} cought {emoji} {type} cat!!!!1!\nYou now have {count} cats of dat type!!!\nthis fella was cought in {time}!!!!"

                view = None
                button = None

                async def dark_market_cutscene(interaction):
                    nonlocal message
                    if interaction.user != message.author:
                        await interaction.response.send_message(
                            "the shadow you saw runs away. perhaps you need to be the one to catch the cat.",
                            ephemeral=True,
                        )
                        return
                    if user.dark_market_active:
                        await interaction.response.send_message("the shadowy figure is nowhere to be found.", ephemeral=True)
                        return
                    user.dark_market_active = True
                    await user.save()
                    await interaction.response.send_message("is someone watching after you?", ephemeral=True)

                    dark_market_followups = [
                        "you walk up to them. the dark voice says:",
                        "**???**: Hello. We have a unique deal for you.",
                        "**???**: To access our services, run /catnip.",
                        "**???**: You won't be disappointed.",
                        "before you manage to process that, the figure disappears. will you figure out whats going on?",
                        "the only choice is to go to that place.",
                    ]

                    for phrase in dark_market_followups:
                        await asyncio.sleep(5)
                        await interaction.followup.send(phrase, ephemeral=True)

                    await achemb(message, "dark_market", "followup")

                vote_time_user = await User.get_or_create(user_id=message.author.id)
                from discord.ui import Button, LayoutView as _LayoutView
                if random.randint(0, 10) == 0 and user.total_catches > 50 and not user.dark_market_active:
                    button = Button(label="You see a shadow...", style=discord.ButtonStyle.red)
                    button.callback = dark_market_cutscene
                elif config.WEBHOOK_VERIFY and vote_time_user.vote_time_topgg + 43200 < time.time():
                    button = Button(
                        emoji=get_emoji("topgg"),
                        label=random.choice(vote_button_texts),
                        url="https://top.gg/bot/1387860417706987590/vote",
                    )
                elif random.randint(0, 20) == 0:
                    button = Button(label="Join our Discord!", url="https://discord.gg/BbDXVm4YTg")
                elif random.randint(0, 500) == 0:
                    button = Button(label="John Discord \U0001f920", url="https://discord.gg/BbDXVm4YTg")
                elif random.randint(0, 50000) == 0:
                    button = Button(
                        label="DAVE DISCORD \U0001f600\U0001f480\u26a0\ufe0f\U0001f97a",
                        url="https://discord.gg/BbDXVm4YTg",
                    )
                elif random.randint(0, 5000000) == 0:
                    button = Button(
                        label="JOHN AND DAVE HAD A SON \U0001f480\U0001f920\U0001f600\u26a0\ufe0f\U0001f97a",
                        url="https://discord.gg/BbDXVm4YTg",
                    )

                if button:
                    view = _LayoutView(timeout=VIEW_TIMEOUT)
                    view.add_item(button)

                user[f"cat_{le_emoji}"] += silly_amount
                new_count = user[f"cat_{le_emoji}"]

                async def delete_cat():
                    try:
                        cat_spawn = send_target.get_partial_message(cat_temp)
                        await cat_spawn.delete()
                    except Exception:
                        pass

                async def send_confirm():
                    try:
                        kwargs = {}
                        if view:
                            kwargs["view"] = view

                        await send_target.send(
                            coughstring.replace("{username}", message.author.name.replace("_", "\\_"))
                            .replace("{emoji}", str(icon))
                            .replace("{type}", le_emoji)
                            .replace("{count}", f"{new_count:,}")
                            .replace("{time}", caught_time[:-1])
                            + suffix_string,
                            **kwargs,
                        )
                    except Exception:
                        pass

                await asyncio.gather(delete_cat(), send_confirm())

                logging.debug("Caught (pre-boost) %d %s", 1, channel.cattype)
                logging.debug("Caught (post-boost) %d %s", silly_amount, le_emoji)

                user.total_catches += 1
                if do_time:
                    user.total_catch_time += time_caught

                if do_time and time_caught < user.time:
                    user.time = time_caught
                if do_time and time_caught > user.timeslow:
                    user.timeslow = time_caught

                if channel.cat_rains > 0:
                    user.rain_participations += 1

                await user.save()

                _is_rain = channel.cat_rains > 0 or cat_rain_end
                if not _is_rain:
                    _ac_react = time_caught if do_time else None
                    _ac_reason = _ac_record_catch(message.author.id, _ac_react)
                    if _ac_reason:
                        shared.bot.loop.create_task(_ac_send_report(
                            user_id=message.author.id,
                            guild_id=message.guild.id,
                            trigger=_ac_reason,
                            context=f"Cat catch \u2014 type: {le_emoji} \u00b7 react time: {f'{time_caught:.3f}s' if do_time else 'N/A'}",
                        ))

                try:
                    guild_str = f"{message.guild.name} ({message.guild.id})" if message.guild else "DM"
                    channel_str = f"#{message.channel.name} ({message.channel.id})"
                    catch_embed = discord.Embed(
                        title=f"\U0001f431 Cat Caught \u2014 {le_emoji}",
                        color=Colors.brown,
                        timestamp=discord.utils.utcnow(),
                    )
                    catch_embed.add_field(name="User", value=f"{message.author} ({message.author.id})", inline=True)
                    catch_embed.add_field(name="Server", value=guild_str, inline=True)
                    catch_embed.add_field(name="Channel", value=channel_str, inline=False)
                    catch_embed.add_field(name="Type", value=le_emoji, inline=True)
                    if silly_amount != 1:
                        catch_embed.add_field(name="Amount", value=str(silly_amount), inline=True)
                    catch_embed.add_field(name="Total of Type", value=f"{new_count:,}", inline=True)
                    if do_time:
                        catch_embed.add_field(name="Catch Time", value=caught_time.strip(), inline=True)
                    if channel.cat_rains > 0 or cat_rain_end:
                        catch_embed.add_field(name="During Rain", value="\u2614 Yes", inline=True)
                    catch_embed.set_footer(text=f"Total Catches: {user.total_catches:,} \u2022 Total Servers: {len(shared.bot.guilds)}")
                    await log_catch(catch_embed)
                except Exception as log_err:
                    logging.warning(f"Catch log failed: {log_err}")

                if random.randint(0, 1000) == 69:
                    await achemb(message, "lucky", "send")
                if message.content == "CAT":
                    await achemb(message, "loud_cat", "send")
                if shared.bot.user in message.mentions and message.reference.message_id == cat_temp:
                    await achemb(message, "ping_reply", "send")
                if channel.cat_rains > 0:
                    await achemb(message, "cat_rain", "send")

                await achemb(message, "first", "send")

                if user.time <= 5:
                    await achemb(message, "fast_catcher", "send")

                if user.timeslow >= 3600:
                    await achemb(message, "slow_catcher", "send")

                if time_caught in [3.14, 31.41, 31.42, 194.15, 194.16, 1901.59, 11655.92, 11655.93]:
                    await achemb(message, "pie", "send")

                if time_caught > 0 and time_caught == int(time_caught):
                    await achemb(message, "perfection", "send")

                if did_boost:
                    await achemb(message, "boosted", "send")

                if "undefined" not in caught_time and time_caught > 0:
                    raw_digits = "".join(char for char in caught_time[:-1] if char.isdigit())
                    if len(set(raw_digits)) == 1:
                        await achemb(message, "all_the_same", "send")

                if suffix_string.count("\n") >= 4:
                    await achemb(message, "certified_yapper", "send")

                await progress(message, user, "3cats")
                if channel.cattype == "Fine":
                    await progress(message, user, "2fine")
                if channel.cattype == "Good":
                    await progress(message, user, "good")
                if time_caught >= 0 and time_caught < 10:
                    await progress(message, user, "under10")
                if time_caught >= 0 and int(time_caught) % 2 == 0:
                    await progress(message, user, "even")
                if time_caught >= 0 and int(time_caught) % 2 == 1:
                    await progress(message, user, "odd")
                if channel.cattype and channel.cattype not in ["Fine", "Nice", "Good"]:
                    await progress(message, user, "rare+")
                if did_boost:
                    await progress(message, user, "prism")
                if user.catch_quest == "finenice":
                    if channel.cattype == "Fine" and user.catch_progress in [0, 2]:
                        await progress(message, user, "finenice")
                    elif channel.cattype == "Nice" and user.catch_progress in [0, 1]:
                        await progress(message, user, "finenice")
                        await progress(message, user, "finenice")

                await bounty(message, user, channel.cattype)
            finally:
                if decided_time:
                    if cat_rain_end:
                        await channel.save()
                        shared.bot.loop.create_task(rain_end(message, channel, force_rain_summary))

                    if decided_time > 10:
                        start_time = channel.yet_to_spawn
                        shifts = [0] + [x for n in range(1, 11) for x in (n, -n)]
                        for shift in shifts:
                            c = await Channel.count("yet_to_spawn = $1", start_time + shift)
                            if c < 5:
                                channel.yet_to_spawn = start_time + shift
                                decided_time += shift
                                break

                    await channel.save()

                    await asyncio.sleep(decided_time)
                    try:
                        temp_catches_storage.remove(pls_remove_me_later_k_thanks)
                    except Exception:
                        pass
                    await spawn_cat(str(message.channel.id))
                else:
                    await channel.save()
                    try:
                        temp_catches_storage.remove(pls_remove_me_later_k_thanks)
                    except Exception:
                        pass

    if message.author.id not in OWNER_IDS:
        return

    if text.lower().startswith("cat!sweep"):
        try:
            channel = await Channel.get_or_none(channel_id=message.channel.id)
            channel.cat = 0
            await channel.save()
            await message.reply("success")
        except Exception:
            pass
    if text.lower().startswith("cat!restart"):
        try:
            await message.reply("restarting!")
        except Exception:
            pass
        try:
            restart_embed = discord.Embed(
                title="\U0001f504 Bot Restarting",
                description="Manual restart triggered via `cat!restart`.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow(),
            )
            restart_embed.add_field(name="Triggered By", value=f"{message.author} ({message.author.id})", inline=True)
            restart_embed.add_field(name="DB Reload", value="Yes" if "db" in text else "No", inline=True)
            restart_embed.add_field(name="Soft uptime", value=f"<t:{int(config.SOFT_RESTART_TIME)}:R>", inline=False)
            await log_uptime(restart_embed)
            await log_dev(restart_embed)
        except Exception as e:
            logging.warning(f"restart log failed: {e}")
        os.system("git pull")
        if config.WEBHOOK_VERIFY:
            await vote_server.cleanup()
        await shared.bot.cat_bot_reload_hook("db" in text)
    if text.lower().startswith("cat!print"):
        try:
            await message.reply(eval(text[9:]))
        except Exception:
            try:
                await message.reply(traceback.format_exc())
            except Exception:
                pass
    if text.lower().startswith("cat!eval"):
        silly_billy = text[9:]

        spaced = ""
        for i in silly_billy.split("\n"):
            spaced += "  " + i + "\n"

        intro = "async def go(message, bot):\n try:\n"
        ending = "\n except Exception:\n  await message.reply(traceback.format_exc())\nbot.loop.create_task(go(message, bot))"

        complete = intro + spaced + ending
        exec(complete)
    if text.lower().startswith("cat!news"):
        async for i in Channel.all():
            try:
                channeley = shared.bot.get_partial_messageable(int(i.channel_id))
                await channeley.send(text[8:])
            except Exception:
                pass
    if text.lower().startswith("cat!custom"):
        stuff = text.split(" ")
        if stuff[1][0] not in "1234567890":
            stuff.insert(1, str(message.channel.id))
        user = await User.get_or_create(user_id=int(stuff[1]))
        cat_name = " ".join(stuff[2:])
        if stuff[2] != "None" and message.reference and message.reference.message_id:
            emoji_name = str(user.user_id) + "cat"
            if emoji_name in emojis.keys():
                await message.reply("emoji already exists")
                return
            og_msg = await message.channel.fetch_message(message.reference.message_id)
            if not og_msg or len(og_msg.attachments) == 0:
                await message.reply("no image found")
                return
            img_data = await og_msg.attachments[0].read()

            if og_msg.attachments[0].content_type.startswith("image/gif"):
                await shared.bot.create_application_emoji(name=emoji_name, image=img_data)
            else:
                img = Image.open(io.BytesIO(img_data))
                img.thumbnail((128, 128))
                with io.BytesIO() as image_binary:
                    img.save(image_binary, format="PNG")
                    image_binary.seek(0)
                    await shared.bot.create_application_emoji(name=emoji_name, image=image_binary.getvalue())
        user.custom = cat_name if cat_name != "None" else ""
        emojis = {emoji.name: str(emoji) for emoji in await shared.bot.fetch_application_emojis()}
        await user.save()
        await message.reply("success")

    if text.lower().startswith("cat!devbackup"):
        await message.reply("\u23f3 Running backup...")
        success, msg = await do_backup()
        status = "\u2705" if success else "\u274c"
        await message.reply(f"{status} {msg}")
        await log_dev_cmd(msg)
        return

    if text.lower().startswith("cat!devrain"):
        parts = text.split()
        if len(parts) < 3:
            await message.reply("Usage: `cat!devrain <user_id> <amount>`")
            return
        try:
            uid = int(parts[1])
            amount = int(parts[2])
        except ValueError:
            await message.reply("\u274c Invalid user_id or amount.")
            return
        if amount <= 0:
            await message.reply("\u274c Amount must be > 0.")
            return
        try:
            _u = await User.get_or_create(user_id=uid)
            if not _u.rain_minutes:
                _u.rain_minutes = 0
            old_minutes = _u.rain_minutes
            _u.rain_minutes += amount
            _u.premium = True
            await _u.save()
            try:
                _du = await shared.bot.fetch_user(uid)
                _uname = str(_du)
            except Exception:
                _uname = f"ID {uid}"
            await message.reply(
                f"\u2705 Gave **{amount}** rain minute(s) to **{_uname}**\n"
                f"They now have **{_u.rain_minutes}** minutes (was {old_minutes})."
            )
            try:
                _re = discord.Embed(title="\u2614 Rain Minutes Added (cat!devrain)", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                _re.add_field(name="User", value=f"{_uname} ({uid})", inline=True)
                _re.add_field(name="Added", value=str(amount), inline=True)
                _re.add_field(name="Previous", value=str(old_minutes), inline=True)
                _re.add_field(name="Total", value=str(_u.rain_minutes), inline=True)
                _re.add_field(name="Added By", value=f"{message.author} ({message.author.id})", inline=False)
                await log_rain(_re)
            except Exception as _le:
                logging.warning(f"cat!devrain log failed: {_le}")
            await log_dev_cmd(f"gave {amount} rain mins to {_uname} ({uid})")
        except Exception:
            await message.reply(f"\u274c Failed:\n```{traceback.format_exc()[:1800]}```")
        return

    if text.lower().startswith("cat!rain"):
        arguements = text.split(" ")

        if len(arguements) < 3:
            await message.reply("Usage: `cat!rain <user_id> short/medium/long/N` or `cat!rain give <user_id> <amount>` or `cat!rain remove <user_id> <amount>`")
            return

        if arguements[1].lower() == "give":
            if len(arguements) < 4:
                await message.reply("Usage: `cat!rain give <user_id> <amount>`")
                return
            try:
                uid = int(arguements[2])
                amount = int(arguements[3])
            except ValueError:
                await message.reply("Invalid user ID or amount.")
                return
            try:
                user = await User.get_or_create(user_id=uid)
                if not user.rain_minutes:
                    user.rain_minutes = 0
                old_minutes = user.rain_minutes
                user.rain_minutes += amount
                user.premium = True
                await user.save()

                try:
                    duser = await shared.bot.fetch_user(uid)
                    uname = str(duser)
                except Exception:
                    uname = f"ID {uid}"

                await message.reply(f"Gave **{amount}** rain minutes to **{uname}** (now has **{user.rain_minutes}**).")

                try:
                    person = await fetch_dm_channel(user)
                    await person.send(
                        f"**You have recieved {amount} minutes of Cat Rain!** \u2614\n\nThanks for your support!\nYou can start a rain with `/rain`. By buying you also get access to `/editprofile` and `/customcat` commands as well as a role in [our Discord server](<https://discord.gg/BbDXVm4YTg>)!\n\nEnjoy your goods!"
                    )
                except Exception:
                    pass

                try:
                    rain_embed = discord.Embed(
                        title="\u2614 Rain Minutes Added",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow(),
                    )
                    rain_embed.add_field(name="User", value=f"{uname} ({uid})", inline=True)
                    rain_embed.add_field(name="Minutes Added", value=str(amount), inline=True)
                    rain_embed.add_field(name="Total Rain Minutes", value=str(user.rain_minutes), inline=True)
                    rain_embed.add_field(name="Added By", value=f"{message.author} ({message.author.id})", inline=False)
                    rain_embed.set_footer(text=f"Total Servers: {len(shared.bot.guilds)}")
                    await log_rain(rain_embed)
                except Exception as log_err:
                    logging.warning(f"Rain add log failed: {log_err}")

                logging.info(f"cat!rain give: {amount} rain mins to {uname} ({uid})")
            except Exception:
                await message.reply(f"Failed:\n```{traceback.format_exc()}```")
            return

        if arguements[1].lower() == "remove":
            if len(arguements) < 4:
                await message.reply("Usage: `cat!rain remove <user_id> <amount>`")
                return
            try:
                uid = int(arguements[2])
                amount = int(arguements[3])
            except ValueError:
                await message.reply("Invalid user ID or amount.")
                return
            try:
                user = await User.get_or_create(user_id=uid)
                if not user.rain_minutes:
                    user.rain_minutes = 0
                old_minutes = user.rain_minutes
                user.rain_minutes = max(0, user.rain_minutes - amount)
                await user.save()

                try:
                    duser = await shared.bot.fetch_user(uid)
                    uname = str(duser)
                except Exception:
                    uname = f"ID {uid}"

                await message.reply(f"Removed **{amount}** rain minutes from **{uname}** (was {old_minutes}, now has **{user.rain_minutes}**).")
                logging.info(f"cat!rain remove: {amount} rain mins from {uname} ({uid})")
            except Exception:
                await message.reply(f"Failed:\n```{traceback.format_exc()}```")
            return

        try:
            uid = int(arguements[1])
            rain_duration = arguements[2]
        except (ValueError, IndexError):
            await message.reply("Usage: `cat!rain <user_id> short/medium/long/N` or `cat!rain give <user_id> <amount>`")
            return

        try:
            user = await User.get_or_create(user_id=uid)
            if not user.rain_minutes:
                user.rain_minutes = 0

            if rain_duration == "short":
                user.rain_minutes += 2
                minutes_added = 2
            elif rain_duration == "medium":
                user.rain_minutes += 10
                minutes_added = 10
            elif rain_duration == "long":
                user.rain_minutes += 20
                minutes_added = 20
            else:
                try:
                    minutes_added = int(rain_duration)
                except ValueError:
                    await message.reply("Invalid duration. Use `short`, `medium`, `long`, or a number.")
                    return
                user.rain_minutes += minutes_added
                user.rain_minutes_bought += minutes_added
            user.premium = True
            await user.save()

            await message.reply(f"Gave **{minutes_added}** rain minutes to <@{uid}> (now has **{user.rain_minutes}**).")

            try:
                person = await fetch_dm_channel(user)
                await person.send(
                    f"**You have recieved {minutes_added} minutes of Cat Rain!** \u2614\n\nThanks for your support!\nYou can start a rain with `/rain`. By buying you also get access to `/editprofile` and `/customcat` commands as well as a role in [our Discord server](<https://discord.gg/BbDXVm4YTg>)!\n\nEnjoy your goods!"
                )
            except Exception:
                pass

            try:
                rain_embed = discord.Embed(
                    title="\u2614 Rain Minutes Added",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow(),
                )
                rain_embed.add_field(name="User ID", value=str(user.user_id), inline=True)
                rain_embed.add_field(name="Minutes Added", value=str(minutes_added), inline=True)
                rain_embed.add_field(name="Total Rain Minutes", value=str(user.rain_minutes), inline=True)
                rain_embed.add_field(name="Added By", value=f"{message.author} ({message.author.id})", inline=False)
                rain_embed.set_footer(text=f"Total Servers: {len(shared.bot.guilds)}")
                await log_rain(rain_embed)
            except Exception as log_err:
                logging.warning(f"Rain add log failed: {log_err}")

            logging.info(f"cat!rain: {minutes_added} rain mins to <@{uid}> (shorthand: {rain_duration})")
        except Exception:
            await message.reply(f"Failed:\n```{traceback.format_exc()}```")

        return

    if text.lower().startswith("cat!devsay"):
        rest = text[len("cat!devsay"):].strip()
        parts = rest.split(None, 1)
        target_ch = message.channel
        msg_text = rest
        if parts and parts[0].lstrip("<#>").isdigit():
            try:
                target_ch = shared.bot.get_channel(int(parts[0].lstrip("<#>"))) or message.channel
                msg_text = parts[1] if len(parts) > 1 else ""
            except Exception:
                pass
        if not msg_text:
            await message.reply("Usage: `cat!devsay [#channel_id] <message>`")
            return
        try:
            await target_ch.send(msg_text)
            await message.reply(f"\u2705 Sent in {target_ch.mention}.")
            await log_dev_cmd(f"said in #{target_ch.name}: {msg_text[:200]}")
        except discord.Forbidden:
            await message.reply(f"\u274c No permission to send in {target_ch.mention}.")
        except Exception:
            await message.reply(f"\u274c Failed:\n```{traceback.format_exc()[:1800]}```")
        return

    if text.lower().startswith("cat!devembed"):
        rest = text[len("cat!devembed"):].strip()
        parts = rest.split(None, 1)
        target_ch = message.channel
        embed_rest = rest
        if parts and parts[0].lstrip("<#>").isdigit():
            try:
                target_ch = shared.bot.get_channel(int(parts[0].lstrip("<#>"))) or message.channel
                embed_rest = parts[1] if len(parts) > 1 else ""
            except Exception:
                pass
        sections = [s.strip() for s in embed_rest.split("|")]
        if len(sections) < 2:
            await message.reply("Usage: `cat!devembed [#channel_id] <title> | <description> [| #rrggbb]`")
            return
        etitle = sections[0]
        edesc = sections[1]
        ecolor = Colors.brown
        if len(sections) >= 3:
            try:
                ecolor = discord.Color(int(sections[2].lstrip("#"), 16))
            except ValueError:
                pass
        try:
            emb = discord.Embed(title=etitle, description=edesc, color=ecolor, timestamp=discord.utils.utcnow())
            emb.set_footer(text=f"Sent by {message.author.display_name}")
            await target_ch.send(embed=emb)
            await message.reply(f"\u2705 Embed sent in {target_ch.mention}.")
            await log_dev_cmd(f"embed in #{target_ch.name}: {etitle}")
        except discord.Forbidden:
            await message.reply(f"\u274c No permission to send in {target_ch.mention}.")
        except Exception:
            await message.reply(f"\u274c Failed:\n```{traceback.format_exc()[:1800]}```")
        return

    if text.lower().startswith("cat!devserverinfo"):
        parts = text.split()
        if len(parts) < 2:
            await message.reply("Usage: `cat!devserverinfo <guild_id>`")
            return
        try:
            gid = int(parts[1])
        except ValueError:
            await message.reply(f"\u274c Invalid guild ID: `{parts[1]}`")
            return
        guild = shared.bot.get_guild(gid)
        if not guild:
            try:
                guild = await shared.bot.fetch_guild(gid)
            except discord.NotFound:
                await message.reply(f"\u274c Server `{gid}` not found.")
                return
            except Exception:
                await message.reply(f"\u274c Failed:\n```{traceback.format_exc()[:1800]}```")
                return
        try:
            db_channels = await Channel.collect("guild_id = $1", str(gid))
            db_channel_count = len(db_channels)
        except Exception:
            db_channel_count = "N/A"
        owner_name = str(guild.owner) if guild.owner else f"ID {guild.owner_id}"
        invite_str = "N/A"
        try:
            chs = [c for c in guild.text_channels if guild.me and c.permissions_for(guild.me).create_instant_invite]
            if chs:
                inv = await chs[0].create_invite(max_age=3600, max_uses=1, reason="cat!devserverinfo")
                invite_str = inv.url
        except Exception:
            pass
        emb = discord.Embed(title=f"\U0001f3e0 Server Info: {guild.name}", color=Colors.brown, timestamp=discord.utils.utcnow())
        if guild.icon:
            emb.set_thumbnail(url=guild.icon.url)
        emb.add_field(name="\U0001f194 ID", value=f"`{guild.id}`", inline=True)
        emb.add_field(name="\U0001f451 Owner", value=f"{owner_name}\n`{guild.owner_id}`", inline=True)
        emb.add_field(name="\U0001f465 Members", value=str(guild.member_count or "?"), inline=True)
        emb.add_field(name="\U0001f4ac Text Channels", value=str(len(guild.text_channels)), inline=True)
        emb.add_field(name="\U0001f431 DB Channels", value=str(db_channel_count), inline=True)
        emb.add_field(name="\U0001f4c5 Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        emb.add_field(name="\U0001f517 Invite (1hr, 1 use)", value=invite_str, inline=False)
        await message.reply(embed=emb)
        await log_dev_cmd(f"server info for {guild.name} ({gid})")
        return

    if text.lower().startswith("cat!devsetcustom"):
        parts = text.split(None, 2)
        if len(parts) < 3:
            await message.reply("Usage: `cat!devsetcustom <user_id> <cat_name|none>`")
            return
        try:
            uid = int(parts[1])
        except ValueError:
            await message.reply(f"\u274c Invalid user ID: `{parts[1]}`")
            return
        cat_name = parts[2]
        clearing = cat_name.lower() == "none"
        try:
            _u = await User.get_or_create(user_id=uid)
            old_custom = _u.custom or "None"
            _u.custom = None if clearing else cat_name
            await _u.save()
            try:
                _du = await shared.bot.fetch_user(uid)
                _uname = str(_du)
            except Exception:
                _uname = f"ID {uid}"
            if clearing:
                await message.reply(f"\u2705 Cleared custom cat for **{_uname}** (was `{old_custom}`).")
            else:
                await message.reply(f"\u2705 Set custom cat for **{_uname}** to `{cat_name}` (was `{old_custom}`).")
            await log_dev_cmd(f"set custom cat for {_uname} ({uid}) to {cat_name!r}")
        except Exception:
            await message.reply(f"\u274c Failed:\n```{traceback.format_exc()[:1800]}```")
        return
