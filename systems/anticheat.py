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
from discord import ButtonStyle
from discord.ui import Button, LayoutView

import config
import shared
from shared import bot, _ac_data
from constants import cattypes
from core.colors import Colors
from database import Profile


_AC_WINDOW = 60
_AC_MAX_CATCHES = 12
_AC_MAX_CASINO = 40
_AC_MIN_REACT = 0.18
_AC_MIN_REACT_RUN = 3


def _ac_record_catch(user_id: int, react_time: float | None) -> str | None:
    """Record a catch event and return a flag reason string if suspicious, else None."""
    now = time.time()
    entry = _ac_data.setdefault(user_id, {"catches": [], "casino": [], "fast_run": 0})

    entry["catches"] = [t for t in entry["catches"] if now - t < _AC_WINDOW]
    entry["catches"].append(now)

    if react_time is not None:
        if react_time < _AC_MIN_REACT:
            entry["fast_run"] += 1
        else:
            entry["fast_run"] = 0

    reasons = []
    if len(entry["catches"]) > _AC_MAX_CATCHES:
        reasons.append(f"**{len(entry['catches'])} catches** in {_AC_WINDOW}s (limit {_AC_MAX_CATCHES})")
    if entry["fast_run"] >= _AC_MIN_REACT_RUN:
        reasons.append(f"**{entry['fast_run']} consecutive catches** under {_AC_MIN_REACT}s react time (last: {react_time:.3f}s)")

    return "; ".join(reasons) if reasons else None


def _ac_record_casino(user_id: int) -> str | None:
    """Record a casino interaction and return a flag reason if suspicious."""
    now = time.time()
    entry = _ac_data.setdefault(user_id, {"catches": [], "casino": [], "fast_run": 0})
    entry["casino"] = [t for t in entry["casino"] if now - t < _AC_WINDOW]
    entry["casino"].append(now)

    if len(entry["casino"]) > _AC_MAX_CASINO:
        return f"**{len(entry['casino'])} casino interactions** in {_AC_WINDOW}s (limit {_AC_MAX_CASINO})"
    return None


async def _ac_send_report(user_id: int, guild_id: int, trigger: str, context: str):
    """Send an anti-cheat report embed with action buttons to the configured channel."""
    channel_id = getattr(config, "ANTICHEAT_CHANNEL_ID", None)
    if not channel_id:
        return

    ch = bot.get_partial_messageable(int(channel_id))

    try:
        discord_user = await bot.fetch_user(user_id)
        user_str = f"{discord_user} (`{user_id}`)"
        avatar = discord_user.display_avatar.url
    except Exception:
        user_str = f"`{user_id}`"
        avatar = None

    try:
        guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
        guild_str = f"{guild.name} (`{guild_id}`)"
    except Exception:
        guild_str = f"`{guild_id}`"

    stats = _ac_data.get(user_id, {})
    catches_60s = len(stats.get("catches", []))
    casino_60s = len(stats.get("casino", []))
    fast_run = stats.get("fast_run", 0)

    embed = discord.Embed(
        title="\U0001f6a8 Anti-Cheat Flag",
        description=(
            f"**User:** {user_str}\n"
            f"**Server:** {guild_str}\n"
            f"**Context:** {context}\n\n"
            f"**Trigger:** {trigger}\n\n"
            f"**60s stats:** {catches_60s} catches \u00b7 {casino_60s} casino interactions \u00b7 "
            f"{fast_run} fast-react streak"
        ),
        color=Colors.red,
        timestamp=discord.utils.utcnow(),
    )
    if avatar:
        embed.set_thumbnail(url=avatar)
    embed.set_footer(text=f"UID {user_id} \u00b7 GID {guild_id}")

    btn_wipe_today = Button(emoji="\U0001f5d1\ufe0f", label="Wipe today's data", style=ButtonStyle.danger)
    btn_wipe_all = Button(label="# Wipe ALL data", style=ButtonStyle.danger)
    btn_blacklist = Button(label="Blacklist user", style=ButtonStyle.danger)
    btn_dismiss = Button(label="Dismiss", style=ButtonStyle.grey)

    async def _wipe_today(i: discord.Interaction):
        try:
            cutoff = int(time.time()) - 86400
            profiles = await Profile.collect("user_id = $1", user_id)
            wiped_guilds = 0
            for p in profiles:
                for cat in cattypes:
                    p[f"cat_{cat}"] = 0
                p.gambles = 0
                await p.save()
                wiped_guilds += 1
            await i.response.send_message(f"Dismissed: Wiped today's cat inventory for `{user_id}` across **{wiped_guilds}** server(s).", ephemeral=True)
        except Exception as e:
            await i.response.send_message(f"Failed: `{e}`", ephemeral=True)

    async def _wipe_all(i: discord.Interaction):
        try:
            profiles = await Profile.collect("user_id = $1", user_id)
            count = len(profiles)
            for p in profiles:
                await p.delete()
            await i.response.send_message(f"Deleted **{count}** profile(s) for `{user_id}`.", ephemeral=True)
        except Exception as e:
            await i.response.send_message(f"Failed: `{e}`", ephemeral=True)

    async def _blacklist(i: discord.Interaction):
        try:
            reason = f"[AntiCheat] Auto-flagged: {trigger}"
            from systems.blacklist import add_to_blacklist
            success = await add_to_blacklist(user_id, "user", reason, i.user.id)
            if success:
                await i.response.send_message(f"`{user_id}` has been blacklisted.", ephemeral=True)
            else:
                await i.response.send_message("User is already blacklisted.", ephemeral=True)
        except Exception as e:
            await i.response.send_message(f"Failed: `{e}`", ephemeral=True)

    async def _dismiss(i: discord.Interaction):
        await i.response.send_message("Report dismissed.", ephemeral=True)

    btn_wipe_today.callback = _wipe_today
    btn_wipe_all.callback = _wipe_all
    btn_blacklist.callback = _blacklist
    btn_dismiss.callback = _dismiss

    view = LayoutView(timeout=86400)
    view.add_item(btn_wipe_today)
    view.add_item(btn_wipe_all)
    view.add_item(btn_blacklist)
    view.add_item(btn_dismiss)

    try:
        await ch.send(embed=embed, view=view)
    except Exception as e:
        logging.error(f"[AntiCheat] Failed to send report: {e}")
