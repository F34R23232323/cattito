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

from typing import Optional, Literal
import asyncio
import datetime
import logging
import math
import random
import time

import discord
from discord import ButtonStyle
from discord.ui import Button, LayoutView, TextDisplay, Container, Section, Thumbnail, ActionRow

from catpg import RawSQL
import shared
import shared
from constants import cattypes, type_dict, battle, VIEW_TIMEOUT, rain_shill, news_list
from core.colors import Colors
from core.utils import get_emoji, do_funny, lb_type_autocomplete, cats_in_server
from database import Profile, User, Prism
from achievements import achemb
from gui.components import Container as CustomContainer, Option, Select


@shared.bot.tree.command(description="View the leaderboards")
@discord.app_commands.rename(leaderboard_type="type")
@discord.app_commands.describe(
    leaderboard_type="The leaderboard type to view!",
    cat_type="The cat type to view (only for the Cats leaderboard)",
    locked="Whether to remove page switch buttons to prevent tampering",
)
@discord.app_commands.autocomplete(cat_type=lb_type_autocomplete)
async def leaderboards(
    message: discord.Interaction,
    leaderboard_type: Optional[Literal["Cats", "Value", "Fast", "Slow", "Cattlepass", "Cookies", "Pig", "Roulette Dollars", "Prisms"]],
    cat_type: Optional[str],
    locked: Optional[bool],
):
    if not leaderboard_type:
        leaderboard_type = "Cats"
    if not locked:
        locked = False
    if cat_type and cat_type not in cattypes + ["All"]:
        await message.response.send_message("invalid cattype", ephemeral=True)
        return

    async def lb_handler(interaction, type, do_edit=None, specific_cat="All"):
        if specific_cat is None:
            specific_cat = "All"

        nonlocal message
        if do_edit is None:
            do_edit = True
        await interaction.response.defer()

        messager = None
        interactor = None

        show_amount = 15

        string = ""
        if type == "Cats":
            unit = "cats"

            if specific_cat != "All":
                result = await Profile.collect_limit(
                    ["user_id", f"cat_{specific_cat}"], f'guild_id = $1 AND "cat_{specific_cat}" > 0 ORDER BY "cat_{specific_cat}" DESC', message.guild.id
                )
                final_value = f"cat_{specific_cat}"
            else:
                cat_columns = [f'CAST("cat_{c}" AS BIGINT)' for c in cattypes]
                sum_expression = RawSQL("(" + " + ".join(cat_columns) + ") AS final_value")
                result = await Profile.collect_limit(["user_id", sum_expression], "guild_id = $1 ORDER BY final_value DESC", message.guild.id)
                final_value = "final_value"

                rarest = None
                for i in cattypes[::-1]:
                    non_zero_count = await Profile.collect_limit("user_id", f'guild_id = $1 AND "cat_{i}" > 0', message.guild.id)
                    if len(non_zero_count) != 0:
                        rarest = i
                        rarest_holder = non_zero_count
                        break

                if rarest and specific_cat != rarest:
                    catmoji = get_emoji(rarest.lower() + "cat")
                    rarest_holder = [f"<@{i.user_id}>" for i in rarest_holder]
                    joined = ", ".join(rarest_holder)
                    if len(rarest_holder) > 10:
                        joined = f"{len(rarest_holder)} people"
                    string = f"Rarest cat: {catmoji} ({joined}'s)\n\n"
        elif type == "Value":
            unit = "value"
            sums = []
            for cat_type in cattypes:
                if not cat_type:
                    continue
                weight = sum(type_dict.values()) / type_dict[cat_type]
                sums.append(f'({weight}) * "cat_{cat_type}"')
            total_sum_expr = RawSQL("(" + " + ".join(sums) + ") AS final_value")
            result = await Profile.collect_limit(["user_id", total_sum_expr], "guild_id = $1 ORDER BY final_value DESC", message.guild.id)
            final_value = "final_value"
        elif type == "Fast":
            unit = "sec"
            result = await Profile.collect_limit(["user_id", "time"], "guild_id = $1 AND time < 99999999999999 ORDER BY time ASC", message.guild.id)
            final_value = "time"
        elif type == "Slow":
            unit = "h"
            result = await Profile.collect_limit(["user_id", "timeslow"], "guild_id = $1 AND timeslow > 0 ORDER BY timeslow DESC", message.guild.id)
            final_value = "timeslow"
        elif type == "Cattlepass":
            start_date = datetime.datetime(2024, 12, 1)
            current_date = discord.utils.utcnow() + datetime.timedelta(hours=4)
            full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
            bp_season = battle["seasons"][str(full_months_passed)]
            if current_date.day < start_date.day:
                full_months_passed -= 1
            result = await Profile.collect_limit(
                ["user_id", "battlepass", "progress"],
                "guild_id = $1 AND season = $2 AND (battlepass > 0 OR progress > 0) ORDER BY battlepass DESC, progress DESC",
                message.guild.id,
                full_months_passed,
            )
            final_value = "battlepass"
        elif type == "Cookies":
            unit = "cookies"
            result = await Profile.collect_limit(["user_id", "cookies"], "guild_id = $1 AND cookies > 0 ORDER BY cookies DESC", message.guild.id)
            string = "Cookie leaderboard updates every 5 min\n\n"
            final_value = "cookies"
        elif type == "Pig":
            unit = "score"
            result = await Profile.collect_limit(
                ["user_id", "best_pig_score"], "guild_id = $1 AND best_pig_score > 0 ORDER BY best_pig_score DESC", message.guild.id
            )
            final_value = "best_pig_score"
        elif type == "Roulette Dollars":
            unit = "cat dollars"
            result = await Profile.collect_limit(
                ["user_id", "roulette_balance"], "guild_id = $1 AND roulette_balance != 100 ORDER BY roulette_balance DESC", message.guild.id
            )
            final_value = "roulette_balance"
        elif type == "Prisms":
            unit = "prisms"
            result = await Prism.collect_limit(
                ["user_id", RawSQL("COUNT(*) as prism_count")],
                "guild_id = $1 GROUP BY user_id ORDER BY prism_count DESC",
                message.guild.id,
                add_primary_key=False,
            )
            final_value = "prism_count"
        else:
            raise ValueError("Invalid leaderboard type")

        interactor_placement = 0
        messager_placement = 0
        for index, position in enumerate(result):
            if position["user_id"] == interaction.user.id:
                interactor_placement = index + 1
                interactor = position[final_value]
                if type == "Cattlepass":
                    if position[final_value] >= len(bp_season):
                        lv_xp_req = 1500
                    else:
                        lv_xp_req = bp_season[int(position[final_value]) - 1]["xp"]
                    interactor_perc = math.floor((100 / lv_xp_req) * position["progress"])
            if interaction.user != message.user and position["user_id"] == message.user.id:
                messager_placement = index + 1
                messager = position[final_value]
                if type == "Cattlepass":
                    if position[final_value] >= len(bp_season):
                        lv_xp_req = 1500
                    else:
                        lv_xp_req = bp_season[int(position[final_value]) - 1]["xp"]
                    messager_perc = math.floor((100 / lv_xp_req) * position["progress"])

        if type == "Slow":
            if interactor:
                interactor = round(interactor / 3600, 2)
            if messager:
                messager = round(messager / 3600, 2)

        if type == "Fast":
            if interactor:
                interactor = round(interactor, 3)
            if messager:
                messager = round(messager, 3)

        if interactor and type != "Fast":
            if interactor <= 0 and type != "Roulette Dollars":
                interactor_placement = 0
            interactor = round(interactor)
        elif interactor and type == "Fast" and interactor >= 99999999999999:
            interactor_placement = 0

        if messager and type != "Fast":
            if messager <= 0 and type != "Roulette Dollars":
                messager_placement = 0
            messager = round(messager)
        elif messager and type == "Fast" and messager >= 99999999999999:
            messager_placement = 0

        emoji = ""
        if type == "Cats" and specific_cat != "All":
            emoji = get_emoji(specific_cat.lower() + "cat")

        current = 1
        leader = False
        for i in result[:show_amount]:
            num = i[final_value]

            if type == "Cattlepass":
                if i[final_value] >= len(bp_season):
                    lv_xp_req = 1500
                else:
                    lv_xp_req = bp_season[int(i[final_value]) - 1]["xp"]
                prog_perc = math.floor((100 / lv_xp_req) * i["progress"])
                string += f"{current}. Level **{num}** *({prog_perc}%)*: <@{i['user_id']}>\n"
            else:
                if type == "Value":
                    if num <= 0:
                        break
                    num = round(num)
                elif type == "Fast" or type == "Slow":
                    if num >= 99999999999999 or num <= 0:
                        break
                    if num >= 31536000:
                        num = round(num / 31536000, 2)
                        unit = "yrs"
                    elif num >= 86400:
                        num = round(num / 86400, 2)
                        unit = "days"
                    elif num >= 3600:
                        num = round(num / 3600, 2)
                        unit = "hrs"
                    elif num >= 60:
                        num = round(num / 60, 2)
                        unit = "mins"
                    elif num >= 1:
                        num = round(num, 2)
                        unit = "sec"
                    else:
                        num = round(num, 3)
                        unit = "sec"
                elif type in ["Cookies", "Cats", "Pig", "Prisms"] and num <= 0:
                    break
                elif type == "Roulette Dollars" and num == 100:
                    break
                string = string + f"{current}. {emoji} **{num:,}** {unit}: <@{i['user_id']}>\n"

            if message.user.id == i["user_id"] and current <= 5:
                leader = True
            current += 1

        if messager_placement > show_amount or interactor_placement > show_amount:
            string = string + "...\n"

            include_interactor = interactor_placement > show_amount and str(interaction.user.id) not in string
            include_messager = messager_placement > show_amount and str(message.user.id) not in string
            interactor_line = ""
            messager_line = ""
            if include_interactor:
                if type == "Cattlepass":
                    interactor_line = f"{interactor_placement}\\. Level **{interactor}** *({interactor_perc}%)*: {interaction.user.mention}\n"
                else:
                    interactor_line = f"{interactor_placement}\\. {emoji} **{interactor:,}** {unit}: {interaction.user.mention}\n"
            if include_messager:
                if type == "Cattlepass":
                    messager_line = f"{messager_placement}\\. Level **{messager}** *({messager_perc}%)*: {message.user.mention}\n"
                else:
                    messager_line = f"{messager_placement}\\. {emoji} **{messager:,}** {unit}: {message.user.mention}\n"

            if messager_placement > interactor_placement:
                string += interactor_line
                string += messager_line
            else:
                string += messager_line
                string += interactor_line

        title = type + " Leaderboard"
        if type == "Cats":
            title = f"{specific_cat} {title}"
        title = "🏅 " + title

        embedVar = discord.Embed(title=title, description=string.rstrip(), color=Colors.brown).set_footer(text=rain_shill)

        global_user = await User.get_or_create(user_id=message.user.id)

        if len(news_list) > len(global_user.news_state.strip()) or "0" in global_user.news_state.strip()[-4:]:
            embedVar.set_author(name=f"{message.user} has unread news! /news")

        myview = LayoutView(timeout=VIEW_TIMEOUT)

        if type == "Cats":
            cats = await cats_in_server(message.guild.id)

            dd_opts = [Option(label="All", emoji=get_emoji("staring_cat"), value="All")]

            for i in cats[:24]:
                dd_opts.append(Option(label=i, emoji=get_emoji(i.lower() + "cat"), value=i))

            dropdown = Select(
                "cat_type_dd",
                placeholder="Select a cat type",
                opts=dd_opts,
                selected=specific_cat,
                on_select=lambda interaction, option: lb_handler(interaction, type, True, option),
                disabled=locked,
            )

        emojied_options = {
            "Cats": "🐈",
            "Value": "🧮",
            "Fast": "⏱️",
            "Slow": "💤",
            "Cattlepass": "⬆️",
            "Cookies": "🍪",
            "Pig": "🎲",
            "Roulette Dollars": "💰",
            "Prisms": get_emoji("prism"),
        }
        options = [Option(label=k, emoji=v) for k, v in emojied_options.items()]
        lb_select = Select(
            "lb_type",
            placeholder=type,
            opts=options,
            on_select=lambda interaction, type: lb_handler(interaction, type, True),
        )

        if not locked:
            myview.add_item(lb_select)
            if type == "Cats":
                myview.add_item(dropdown)

        try:
            if not do_edit:
                raise Exception
            await interaction.edit_original_response(embed=embedVar, view=myview)
        except Exception:
            await interaction.followup.send(embed=embedVar, view=myview)

        if leader:
            await achemb(message, "leader", "followup")

    await lb_handler(message, leaderboard_type, False, cat_type)
