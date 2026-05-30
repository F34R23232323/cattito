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

import discord

import shared
from constants import total_commands_used
from core.logging_setup import log_guild_join, log_guild_leave
from systems.blacklist import check_guild_blacklist


@shared.bot.event
async def on_guild_join(guild):
    if await check_guild_blacklist(guild.id):
        return

    def verify(ch):
        return ch and ch.permissions_for(guild.me).send_messages

    def find(patt, channels):
        for i in channels:
            if patt in i.name:
                return i

    logging.debug("Guild joined, member count %d", guild.member_count)

    try:
        online = sum(1 for m in guild.members if m.status != discord.Status.offline) if guild.members else guild.member_count
        invite_url = "No invite available"
        try:
            invites = await guild.invites()
            if invites:
                invite_url = invites[0].url
        except Exception:
            pass

        owner_name = str(guild.owner) if guild.owner else f"ID {guild.owner_id}"
        inviter_str = "Unknown"
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
                if entry.target and entry.target.id == shared.bot.user.id:
                    inviter_str = f"{entry.user} ({entry.user.id})"
                    break
        except Exception:
            pass

        embed = discord.Embed(
            title=f"Joined new server: {guild.name}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=owner_name, inline=False)
        embed.add_field(name="Inviter", value=inviter_str, inline=False)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Online Members", value=str(online), inline=True)
        embed.add_field(name="Boosts", value=f"{guild.premium_subscription_count} (Level {guild.premium_tier})", inline=True)
        embed.add_field(name="Verification Level", value=str(guild.verification_level.value), inline=True)
        embed.add_field(name="Server ID", value=str(guild.id), inline=False)
        embed.add_field(name="Created At", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=False)
        embed.add_field(name="Partnered | Verified", value=f"{'Yes' if 'PARTNERED' in guild.features else 'No'} | {'Yes' if 'VERIFIED' in guild.features else 'No'}", inline=False)
        embed.add_field(name="Invite", value=invite_url, inline=False)
        embed.set_footer(text=f"Total Commands: {total_commands_used} • Total Servers: {len(shared.bot.guilds)}")
        await log_guild_join(embed)
    except Exception as e:
        logging.warning(f"Guild join log failed: {e}")

    ch = find("cat", guild.text_channels)
    if not verify(ch):
        ch = find("bot", guild.text_channels)
    if not verify(ch):
        ch = find("commands", guild.text_channels)
    if not verify(ch):
        ch = find("general", guild.text_channels)

    found = False
    if not verify(ch):
        for ch in guild.text_channels:
            if verify(ch):
                found = True
                break
        if not found:
            ch = guild.owner

    unofficial_note = "**NOTE: This is an unofficial cattito instance.**\n\n"
    if not shared.bot.user or shared.bot.user.id == 1387860417706987590:
        unofficial_note = ""
    try:
        if ch.permissions_for(guild.me).send_messages:
            await ch.send(
                unofficial_note
                + "Thanks for adding me!\nTo start, use `/setup` and `/help` to learn more!\nJoin the support server here: https://discord.gg/kyynVDzcJs\nHave a nice day :)"
            )
    except Exception:
        pass


@shared.bot.event
async def on_guild_remove(guild):
    logging.debug("Guild removed, id %d", guild.id)
    try:
        online = sum(1 for m in guild.members if m.status != discord.Status.offline) if guild.members else guild.member_count
        owner_name = str(guild.owner) if guild.owner else f"ID {guild.owner_id}"

        embed = discord.Embed(
            title=f"Left server: {guild.name}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=owner_name, inline=False)
        embed.add_field(name="Members at removal", value=str(guild.member_count), inline=True)
        embed.add_field(name="Online Members", value=str(online), inline=True)
        embed.add_field(name="Boosts", value=f"{guild.premium_subscription_count} (Level {guild.premium_tier})", inline=True)
        embed.add_field(name="Verification Level", value=str(guild.verification_level.value), inline=True)
        embed.add_field(name="Server ID", value=str(guild.id), inline=False)
        embed.add_field(name="Created At", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=False)
        embed.add_field(name="Partnered | Verified", value=f"{'Yes' if 'PARTNERED' in guild.features else 'No'} | {'Yes' if 'VERIFIED' in guild.features else 'No'}", inline=False)
        embed.add_field(name="Roles | Emojis", value=f"{len(guild.roles)} | {len(guild.emojis)}", inline=False)
        embed.set_footer(text=f"Total Commands: {total_commands_used} • Total Servers: {len(shared.bot.guilds)}")
        await log_guild_leave(embed)
    except Exception as e:
        logging.warning(f"Guild remove log failed: {e}")
