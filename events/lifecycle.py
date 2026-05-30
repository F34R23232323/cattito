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
import logging

import aiohttp as _aiohttp
import discord

import config
import shared
from shared import OWNER_IDS, on_ready_debounce, gen_credits
import shared
from constants import testers
from core.logging_setup import _webhook_log_handler, log_uptime


@shared.bot.event
async def on_connect():
    if not shared.emojis:
        fetched = {e.name: str(e) for e in await shared.bot.fetch_application_emojis()}
        shared.emojis.clear()
        shared.emojis.update(fetched)

    try:
        embed = discord.Embed(
            title="\U0001f50c Bot Connected",
            description="Connected (or reconnected) to Discord gateway.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Shard Count", value=str(getattr(shared.bot, "shard_count", 1) or 1), inline=True)
        embed.add_field(name="Servers", value=str(len(shared.bot.guilds)), inline=True)
        await log_uptime(embed)
    except Exception as e:
        logging.warning(f"on_connect uptime log failed: {e}")


@shared.bot.event
async def on_disconnect():
    try:
        embed = discord.Embed(
            title="\u26a1 Bot Disconnected",
            description="Lost connection to the Discord gateway. Will attempt to reconnect automatically.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Uptime (soft)", value=f"<t:{int(config.SOFT_RESTART_TIME)}:R>", inline=True)
        embed.add_field(name="Servers", value=str(len(shared.bot.guilds)), inline=True)
        await log_uptime(embed)
    except Exception as e:
        logging.warning(f"on_disconnect uptime log failed: {e}")


@shared.bot.event
async def on_resumed():
    try:
        embed = discord.Embed(
            title="\u2705 Session Resumed",
            description="Successfully resumed the Discord gateway session after a disconnect.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Servers", value=str(len(shared.bot.guilds)), inline=True)
        await log_uptime(embed)
    except Exception as e:
        logging.warning(f"on_resumed uptime log failed: {e}")


@shared.bot.event
async def on_ready():
    global on_ready_debounce, gen_credits

    if on_ready_debounce:
        return
    on_ready_debounce = True

    logging.info("cat is now online")

    if not _webhook_log_handler._task:
        root_logger = logging.getLogger()
        if _webhook_log_handler not in root_logger.handlers:
            root_logger.addHandler(_webhook_log_handler)
        _webhook_log_handler.start(asyncio.get_event_loop())

    try:
        embed = discord.Embed(
            title="\U0001f680 Bot Ready",
            description=f"**{shared.bot.user}** is fully online and ready.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Servers", value=str(len(shared.bot.guilds)), inline=True)
        embed.add_field(name="Shards", value=str(getattr(shared.bot, "shard_count", 1) or 1), inline=True)
        embed.add_field(name="Hard uptime start", value=f"<t:{int(config.HARD_RESTART_TIME)}:R>", inline=False)
        embed.add_field(name="Latency", value=f"{round(shared.bot.latency * 1000)}ms", inline=True)
        await log_uptime(embed)
    except Exception as e:
        logging.warning(f"on_ready uptime log failed: {e}")

    if not shared.emojis:
        fetched = {e.name: str(e) for e in await shared.bot.fetch_application_emojis()}
        shared.emojis.clear()
        shared.emojis.update(fetched)

    logging.info(f"OWNER_IDS hardcoded to {OWNER_IDS}")

    url = "https://api.github.com/repos/milenakos/cat-bot/contributors"
    contributors = []

    try:
        async with _aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}) as response:
                if response.status == 200:
                    data = await response.json()
                    for contributor in data:
                        login = contributor["login"].replace("_", r"\_")
                        if login not in ["milenakos", "ImgBotApp"]:
                            contributors.append(login)
                else:
                    logging.warning(f"Error: {response.status} - {await response.text()}")
    except Exception as e:
        logging.warning(f"Could not fetch GitHub contributors: {e}")

    tester_users = []
    try:
        for i in testers:
            user = await shared.bot.fetch_user(i)
            tester_users.append(user.name.replace("_", r"\_"))
    except Exception:
        pass

    shared.gen_credits["text"] = "\n".join(
        [
            "Made by **Lia Milenakos**",
            "With contributions from **" + ", ".join(contributors) + "**",
            "Original Cat Image: **pathologicals**",
            "APIs: **catfact.ninja, weilbyte.dev, wordnik.com, thecatapi.com**",
            "Open Source Projects: **[discord.py](https://github.com/Rapptz/discord.py), [asyncpg](https://github.com/MagicStack/asyncpg), [gateway-proxy](https://github.com/Gelbpunkt/gateway-proxy)**",
            "Art, suggestions, and a lot more: **TheTrashCell**",
            "Banner art: **2braincelledcreature**",
            "Testers: **" + ", ".join(tester_users) + "**",
            "Enjoying the bot: **You <3**",
        ]
    )

    try:
        backupchannel_id = int(config.BACKUP_ID)
        try:
            import exportbackup
        except ImportError:
            exportbackup = None
        from loops.backup import backup_task
        shared.bot.loop.create_task(backup_task(shared.bot, backupchannel_id, exportbackup))
        logging.info("Daily backup task started")
    except Exception as e:
        logging.warning(f"Could not start backup task: {e}")


@shared.bot.event
async def on_error(*args, **kwargs):
    raise
