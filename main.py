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
import time
import types

import discord
from aiohttp import web
from discord.ext import commands as dpy_commands

import config
import shared
import constants

# ---------------------------------------------------------------------------
# Apply Discord.py monkeypatches for LayoutView container support
# ---------------------------------------------------------------------------
from gui.monkeypatch import apply_monkeypatches
apply_monkeypatches()

# ---------------------------------------------------------------------------
# Wire tree-level callbacks
# ---------------------------------------------------------------------------
def _wire_tree(b):
    from systems.blacklist import global_interaction_check

    b.tree.interaction_check = global_interaction_check
    b.tree.on_error = events.message_handler.on_app_command_error

    original_call = b.tree._call.__func__

    async def _patched_call(self, interaction: discord.Interaction):
        try:
            await original_call(self, interaction)
        except Exception:
            raise
        else:
            if interaction.type == discord.InteractionType.application_command:
                try:
                    await events.message_handler.on_app_command_completion(interaction)
                except Exception as e:
                    logging.warning(f"on_app_command_completion hook failed: {e}")

    b.tree._call = types.MethodType(_patched_call, b.tree)


# ---------------------------------------------------------------------------
# Import all sub-modules (triggers command registration on shared.bot)
# ---------------------------------------------------------------------------
import systems.blacklist
import systems.anticheat
import systems.xp_bonus

import events.lifecycle
import events.guild_events
import events.message_handler

import loops.background
import loops.backup
import loops.spawning

import catnip.bounties
import catnip.perks
import catnip.cutscenes

import achievements

import webhooks.vote_server

_wire_tree(shared.bot._real)

import commands.admin
import commands.info
import commands.catching
import commands.inventory
import commands.games
import commands.gambling
import commands.misc
import commands.leaderboards
import commands.battlepass_cmd

from core.logging_setup import _webhook_log_handler, log_uptime


# ---------------------------------------------------------------------------
# Extension setup / teardown
# ---------------------------------------------------------------------------
async def setup(bot2):
    vote_server = None

    for command in shared.bot._real.tree.walk_commands():
        command.guild_only = True
        bot2.tree.add_command(command)

    context_menu_command = discord.app_commands.ContextMenu(
        name="catch",
        callback=commands.catching.catch,
    )
    context_menu_command.guild_only = True
    bot2.tree.add_command(context_menu_command)

    _wire_tree(bot2)

    bot2.on_ready = events.lifecycle.on_ready
    bot2.on_guild_join = events.guild_events.on_guild_join
    bot2.on_guild_remove = events.guild_events.on_guild_remove
    bot2.on_message = events.message_handler.on_message
    bot2.on_connect = events.lifecycle.on_connect
    bot2.on_disconnect = events.lifecycle.on_disconnect
    bot2.on_resumed = events.lifecycle.on_resumed
    bot2.on_error = events.lifecycle.on_error

    if config.WEBHOOK_VERIFY:
        app = web.Application()
        app.add_routes([
            web.post("/", webhooks.vote_server.recieve_vote),
            web.get("/supporter", webhooks.vote_server.check_supporter),
            web.get("/uptime", webhooks.vote_server.uptime_handler),
        ])
        vote_server = web.AppRunner(app)
        await vote_server.setup()
        site = web.TCPSite(vote_server, "127.0.0.1", 4446)
        await site.start()

    shared.bot._set(bot2)
    shared.vote_server = vote_server

    config.SOFT_RESTART_TIME = time.time()

    app_commands_synced = await bot2.tree.sync()
    for i in app_commands_synced:
        if i.name == "rain":
            shared.RAIN_ID = i.id

    if bot2.is_ready() and not shared.on_ready_debounce:
        await events.lifecycle.on_ready()


async def teardown(bot2):
    from database import Profile

    cookie_updates = []
    for cookie_id, cookies in shared.temp_cookie_storage.items():
        p = await Profile.get_or_create(guild_id=cookie_id[0], user_id=cookie_id[1])
        p.cookies = cookies
        cookie_updates.append(p)
    if cookie_updates:
        await Profile.bulk_update(cookie_updates, "cookies")

    if config.WEBHOOK_VERIFY and shared.vote_server:
        try:
            await shared.vote_server.cleanup()
        except Exception:
            pass

    try:
        await _webhook_log_handler._flush()
    except Exception:
        pass

    try:
        embed = discord.Embed(
            title="\U0001f6d1 Bot Shutting Down",
            description="Teardown called \u2014 bot is stopping.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Soft uptime", value=f"<t:{int(config.SOFT_RESTART_TIME)}:R>", inline=True)
        embed.add_field(name="Hard uptime", value=f"<t:{int(config.HARD_RESTART_TIME)}:R>", inline=True)
        embed.add_field(name="Servers", value=str(len(shared.bot.guilds)), inline=True)
        await log_uptime(embed)
    except Exception:
        pass
