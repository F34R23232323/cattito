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

from typing import Optional
import asyncio, logging, random, time
import discord, msg2img
from discord import ButtonStyle
from discord.ui import Button, LayoutView, TextDisplay, Section, Container, Thumbnail, ActionRow
import shared
from shared import catchcooldown
import shared
from constants import cattypes, type_dict, VIEW_TIMEOUT
from core.colors import Colors
from core.utils import get_emoji, do_funny
from database import Channel, Profile
from achievements import achemb

fakecooldown: dict = {}


async def catch(message: discord.Interaction, msg: discord.Message):
    if message.user.id in catchcooldown and catchcooldown[message.user.id] + 6 > time.time():
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return
    await message.response.defer()

    event_loop = asyncio.get_event_loop()
    try:
        member = await message.guild.fetch_member(msg.author.id)
    except Exception:
        member = msg.author
    result = await event_loop.run_in_executor(None, msg2img.msg2img, msg, member)

    try:
        await message.followup.send("cought in 4k", file=result)
    except Exception:
        try:
            await message.followup.send("failed")
        except Exception:
            pass

    catchcooldown[message.user.id] = time.time()

    await achemb(message, "4k", "followup")

    if msg.author.id == shared.bot.user.id and "cought in 4k" in msg.content:
        await achemb(message, "8k", "followup")

    try:
        is_cat = (await Channel.get_or_none(channel_id=message.channel.id)).cat
    except Exception:
        is_cat = False

    if int(is_cat) == int(msg.id):
        await achemb(message, "not_like_that", "followup")


@shared.bot.tree.command(name="catch", description="Catch someone in 4k")
async def catch_tip(message: discord.Interaction):
    await message.response.send_message(
        f'Nope, that\'s the wrong way to do this.\nRight Click/Long Hold a message you want to catch > Select `Apps` in the popup > "{get_emoji("staring_cat")} catch"',
        ephemeral=True,
    )


@shared.bot.tree.command(description="LMAO TROLLED SO HARD :JOY:")
async def fake(message: discord.Interaction):
    if message.user.id in fakecooldown and fakecooldown[message.user.id] + 60 > time.time():
        await message.response.send_message("your phone is overheating bro chill", ephemeral=True)
        return
    file = discord.File("images/australian cat.png", filename="australian cat.png")
    icon = get_emoji("egirlcat")
    fakecooldown[message.user.id] = time.time()
    try:
        await message.response.send_message(
            str(icon) + ' eGirl cat hasn\'t appeared! Type "cat" to catch ratio!',
            file=file,
        )
    except Exception:
        await message.response.send_message("i dont have perms lmao here is the ach anyways", ephemeral=True)
        pass
    await achemb(message, "trolled", "ephemeral")


@shared.bot.tree.command(description="View when the last cat was caught in this channel, and when the next one might spawn")
async def last(message: discord.Interaction):
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    nextpossible = ""

    try:
        lasttime = channel.lastcatches
        if int(lasttime) == 0:  # unix epoch check
            displayedtime = "forever ago"
        else:
            displayedtime = f"<t:{int(lasttime)}:R>"
    except Exception:
        displayedtime = "forever ago"

    if channel and not channel.cat:
        times = [channel.spawn_times_min, channel.spawn_times_max]
        nextpossible = f"\nthe next cat will spawn between <t:{int(lasttime) + times[0]}:R> and <t:{int(lasttime) + times[1]}:R>"

    if channel and channel.cat_rains:
        nextpossible += f"\ncat rain! {channel.cat_rains} cats remaining..."

    await message.response.send_message(f"the last cat in this channel was caught {displayedtime}.{nextpossible}")


@shared.bot.tree.command(description="View all the juicy numbers behind cat types")
async def catalogue(message: discord.Interaction):
    fields = []
    for cat_type in cattypes:
        in_server = await Profile.sum(f"cat_{cat_type}", f'guild_id = $1 AND "cat_{cat_type}" > 0', message.guild.id)
        title = f"{get_emoji(cat_type.lower() + 'cat')} {cat_type}"
        if in_server == 0 or not in_server:
            in_server = 0
            title = f"{get_emoji('mysterycat')} ???"
        title += f" ({round((type_dict[cat_type] / sum(type_dict.values())) * 100, 2)}%)"
        fields.append((title, f"{round(sum(type_dict.values()) / type_dict[cat_type], 2)} value\n{in_server:,} in this server"))

    # Split into pages of up to 25 fields
    pages = [fields[i:i + 25] for i in range(0, len(fields), 25)]
    current_page = [0]

    def make_catalogue_view(page_idx):
        page = pages[page_idx]
        lines = "\n".join(f"**{name}** — {value}" for name, value in page)
        title_suffix = f" (Page {page_idx + 1}/{len(pages)})" if len(pages) > 1 else ""
        container = Container(
            f"## {get_emoji('staring_cat')} The Catalogue{title_suffix}",
            lines,
            accent_color=Colors.brown,
        )
        view = LayoutView(timeout=VIEW_TIMEOUT)
        view.add_item(container)
        if len(pages) > 1:
            prev_btn = Button(label="◀ Prev", style=ButtonStyle.secondary, disabled=(page_idx == 0))
            next_btn = Button(label="Next ▶", style=ButtonStyle.secondary, disabled=(page_idx == len(pages) - 1))

            async def prev_page(interaction: discord.Interaction):
                current_page[0] -= 1
                await interaction.response.edit_message(view=make_catalogue_view(current_page[0]))

            async def next_page(interaction: discord.Interaction):
                current_page[0] += 1
                await interaction.response.edit_message(view=make_catalogue_view(current_page[0]))

            prev_btn.callback = prev_page
            next_btn.callback = next_page
            view.add_item(ActionRow(prev_btn, next_btn))
        return view

    await message.response.send_message(view=make_catalogue_view(0))
