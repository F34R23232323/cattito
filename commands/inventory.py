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
import asyncio, logging, math, random, re, time, datetime
import discord, discord_emoji
from discord import ButtonStyle
from discord.ui import (
    Button, LayoutView, Modal, TextInput, TextDisplay, Container,
    Section, Thumbnail, ActionRow, MediaGallery, Select,
)

import config
import shared
from shared import emojis, temp_cookie_storage
import shared
from constants import (
    cattypes, type_dict, pack_data, prism_names, allowedemojis,
    VIEW_TIMEOUT, rain_shill, news_list, battle, ach_list, ach_names,
    cattype_lc_dict,
)
from core.colors import Colors
from core.utils import get_emoji, do_funny, fetch_dm_channel, gift_autocomplete, cats_in_server
from database import Channel, Profile, User, Prism, Server
from achievements import achemb, progress
from core.logging_setup import log_rain
from achievements import refresh_quests, debt_cutscene


# ───────────────────────────────────────────────────────────────────────
#  gen_stats  —  generate stat list for inventory / /stats
# ───────────────────────────────────────────────────────────────────────

async def gen_stats(profile, star):
    stats = []
    user = await User.get_or_create(user_id=profile.user_id)

    # catching
    stats.append([get_emoji("staring_cat"), "Catching"])
    stats.append(["catches", "🐈", f"Catches: {profile.total_catches:,}{star}"])
    catch_time = "---" if profile.time >= 99999999999999 else round(profile.time, 3)
    slow_time = "---" if profile.timeslow == 0 else round(profile.timeslow / 3600, 2)
    stats.append(["time_records", "⏱️", f"Fastest: {catch_time}s, Slowest: {slow_time}h"])
    if profile.total_catches - profile.rain_participations != 0:
        stats.append(
            ["average_time", "⏱️", f"Average catch time: {profile.total_catch_time / (profile.total_catches - profile.rain_participations):,.2f}s{star}"]
        )
    else:
        stats.append(["average_time", "⏱️", f"Average catch time: N/A{star}"])
    stats.append(["purrfect_catches", "✨", f"Purrfect catches: {profile.perfection_count:,}{star}"])

    # catching boosts
    stats.append([get_emoji("prism"), "Boosts"])
    prisms_crafted = await Prism.count("guild_id = $1 AND user_id = $2", profile.guild_id, profile.user_id)
    boosts_done = await Prism.sum("catches_boosted", "guild_id = $1 AND user_id = $2", profile.guild_id, profile.user_id)
    stats.append(["prism_crafted", get_emoji("prism"), f"Prisms crafted: {prisms_crafted:,}"])
    stats.append(["boosts_done", get_emoji("prism"), f"Boosts by owned prisms: {boosts_done:,}{star}"])
    stats.append(["boosted_catches", get_emoji("prism"), f"Prism-boosted catches: {profile.boosted_catches:,}{star}"])

    # catnip
    stats.append([get_emoji("catnip"), "Catnip"])
    stats.append(["catnip_activations", get_emoji("catnip"), f"Cats gained from catnip: {profile.catnip_activations:,}"])
    stats.append(["catnip_bought", get_emoji("catnip"), f"Catnip levels reached: {profile.catnip_bought:,}"])
    stats.append(["highest_catnip_level", "⬆️", f"Highest catnip level: {profile.highest_catnip_level:,}"])
    stats.append(["bounties_complete", "🎯", f"Bounties completed: {profile.bounties_complete:,}"])

    # voting
    stats.append([get_emoji("topgg"), "Voting"])
    stats.append(["total_votes", get_emoji("topgg"), f"Total votes: {user.total_votes:,}{star}"])
    stats.append(["current_vote_streak", "🔥", f"Current vote streak: {user.vote_streak} (max {max(user.vote_streak, user.max_vote_streak):,}){star}"])
    if user.vote_time_topgg + 43200 > time.time():
        stats.append(["can_vote", get_emoji("topgg"), f"Can vote <t:{user.vote_time_topgg + 43200}:R>"])
    else:
        stats.append(["can_vote", get_emoji("topgg"), "Can vote!"])

    # battlepass
    stats.append(["⬆️", "Cattlepass"])
    seasons_complete = 0
    levels_complete = 0
    max_level = 0
    total_xp = 0
    # past seasons
    for season in profile.bp_history.split(";"):
        if not season:
            break
        season_num, season_lvl, season_progress = map(int, season.split(","))
        if season_num == 0:
            continue
        levels_complete += season_lvl
        total_xp += season_progress
        if season_lvl > 30:
            seasons_complete += 1
            total_xp += 1500 * (season_lvl - 31)
        if season_lvl > max_level:
            max_level = season_lvl

        for num, level in enumerate(battle["seasons"][str(season_num)]):
            if num >= season_lvl:
                break
            total_xp += level["xp"]
    # current season
    if profile.season != 0:
        levels_complete += profile.battlepass
        total_xp += profile.progress
        if profile.battlepass > 30:
            seasons_complete += 1
            total_xp += 1500 * (profile.battlepass - 31)
        if profile.battlepass > max_level:
            max_level = profile.battlepass

        for num, level in enumerate(battle["seasons"][str(profile.season)]):
            if num >= profile.battlepass:
                break
            total_xp += level["xp"]
    current_packs = 0
    for pack in pack_data:
        current_packs += profile[f"pack_{pack['name'].lower()}"]
    stats.append(["quests_completed", "✅", f"Quests completed: {profile.quests_completed:,}{star}"])
    stats.append(["seasons_completed", "🏅", f"Cattlepass seasons completed: {seasons_complete:,}"])
    stats.append(["levels_completed", "✅", f"Cattlepass levels completed: {levels_complete:,}"])
    stats.append(["packs_in_inventory", get_emoji("woodenpack"), f"Packs in inventory: {current_packs:,}"])
    stats.append(["packs_opened", get_emoji("goldpack"), f"Packs opened: {profile.packs_opened:,}"])
    stats.append(["pack_upgrades", get_emoji("diamondpack"), f"Pack upgrades: {profile.pack_upgrades:,}"])
    stats.append(["highest_ever_level", "🏆", f"Highest ever Cattlepass level: {max_level:,}"])
    stats.append(["total_xp_earned", "🧮", f"Total Cattlepass XP earned: {total_xp:,}"])

    # rains & supporter
    stats.append(["☔", "Rains"])
    stats.append(["current_rain_minutes", "☔", f"Current rain minutes: {user.rain_minutes:,}"])
    stats.append(["supporter", "👑", "Ever bought rains: " + ("Yes" if user.premium else "No")])
    stats.append(["rain_minutes_bought", "☔", f"Rain minutes bought: {user.rain_minutes_bought:,}"])
    stats.append(["cats_caught_during_rains", "☔", f"Cats caught during rains: {profile.rain_participations:,}{star}"])
    stats.append(["rain_minutes_started", "☔", f"Rain minutes started: {profile.rain_minutes_started:,}{star}"])
    stats.append(["cats_blessed", "🌠", f"Cats blessed: {user.cats_blessed:,}"])

    # gambling
    stats.append(["🎰", "Gambling"])
    stats.append(["casino_spins", "🎰", f"Casino spins: {profile.gambles:,}"])
    stats.append(["slot_spins", "🎰", f"Slot spins: {profile.slot_spins:,}"])
    stats.append(["slot_wins", "🎰", f"Slot wins: {profile.slot_wins:,}"])
    stats.append(["slot_big_wins", "🎰", f"Slot big wins: {profile.slot_big_wins:,}"])
    stats.append(["roulette_spins", "💰", f"Roulette spins: {profile.roulette_spins:,}"])
    stats.append(["roulette_wins", "💰", f"Roulette wins: {profile.roulette_wins:,}"])

    # tic tac toe
    stats.append(["⭕", "Tic Tac Toe"])
    stats.append(["ttc_games", "⭕", f"Tic Tac Toe games played: {profile.ttt_played:,}"])
    stats.append(["ttc_wins", "⭕", f"Tic Tac Toe wins: {profile.ttt_won:,}"])
    stats.append(["ttc_draws", "⭕", f"Tic Tac Toe draws: {profile.ttt_draws:,}"])
    if profile.ttt_played != 0:
        stats.append(["ttc_win_rate", "⭕", f"Tic Tac Toe win rate: {(profile.ttt_won + profile.ttt_draws) / profile.ttt_played * 100:.2f}%"])
    else:
        stats.append(["ttc_win_rate", "⭕", "Tic Tac Toe win rate: 0%"])

    if (profile.guild_id, profile.user_id) not in temp_cookie_storage.keys():
        cookies = profile.cookies
    else:
        cookies = temp_cookie_storage[(profile.guild_id, profile.user_id)]
    # misc
    stats.append(["❓", "Misc"])
    stats.append(["facts_read", "🧐", f"Facts read: {profile.facts:,}"])
    stats.append(["cookies", "🍪", f"Cookies clicked: {cookies:,}"])
    stats.append(["pig_high_score", "🎲", f"Pig high score: {profile.best_pig_score:,}"])
    stats.append(["private_embed_clicks", get_emoji("pointlaugh"), f"Private embed clicks: {profile.funny:,}"])
    stats.append(["reminders_set", "⏰", f"Reminders set: {profile.reminders_set:,}{star}"])
    stats.append(["cats_gifted", "🎁", f"Cats gifted: {profile.cats_gifted:,}{star}"])
    stats.append(["cats_received_as_gift", "🎁", f"Cats received as gift: {profile.cat_gifts_recieved:,}{star}"])
    stats.append(["trades_completed", "💱", f"Trades completed: {profile.trades_completed}{star}"])
    stats.append(["cats_traded", "💱", f"Cats traded: {profile.cats_traded:,}{star}"])
    if profile.user_id == 1075077561454973020:
        stats.append(["owner", get_emoji("neocat"), "a cute catgirl :3"])
    return stats


# ───────────────────────────────────────────────────────────────────────
#  /stats
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(name="stats", description="View some advanced stats")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="Person to view the stats of!")
async def stats_command(message: discord.Interaction, person_id: Optional[discord.User]):
    await message.response.defer()
    if not person_id:
        person_id = message.user
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    star = "*" if not profile.new_user else ""

    stats = await gen_stats(profile, star)
    stats_string = ""
    for stat in stats:
        if len(stat) == 2:
            # category
            stats_string += f"\n{stat[0]} __{stat[1]}__\n"
        elif len(stat) == 3:
            # stat
            stats_string += f"{stat[2]}\n"
    if star:
        stats_string += "\n\\*this stat is only tracked since February 2025"

    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(Container(
        Section(
            TextDisplay(f"## {person_id.name}'s Stats\n{stats_string}"),
            Thumbnail(person_id.display_avatar.url),
        ),
        accent_color=Colors.brown,
    ))
    await message.followup.send(view=view)


# ───────────────────────────────────────────────────────────────────────
#  gen_inventory  —  generate inventory embed for /inventory
# ───────────────────────────────────────────────────────────────────────

async def gen_inventory(message, person_id):
    # check if we are viewing our own inv or some other person
    if person_id is None:
        person_id = message.user
    me = bool(person_id == message.user)
    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user = await User.get_or_create(user_id=person_id.id)

    # around here we count aches
    unlocked = 0
    minus_achs = 0
    minus_achs_count = 0
    for k in ach_names:
        is_ach_hidden = ach_list[k]["category"] == "Hidden"
        if is_ach_hidden:
            minus_achs_count += 1
        if person[k]:
            if is_ach_hidden:
                minus_achs += 1
            else:
                unlocked += 1
    total_achs = len(ach_list) - minus_achs_count
    minus_achs = "" if minus_achs == 0 else f" + {minus_achs}"

    # count prism stuff
    prisms = await Prism.collect_limit(["name"], "guild_id = $1 AND user_id = $2", message.guild.id, person_id.id)
    total_count = await Prism.count("guild_id = $1", message.guild.id)
    user_count = len(prisms)
    global_boost = 0.06 * math.log(2 * total_count + 1)
    prism_boost = round((global_boost + 0.03 * math.log(2 * user_count + 1)) * 100, 3)
    if len(prisms) == 0:
        prism_list = "None"
    elif len(prisms) <= 3:
        prism_list = ", ".join([i.name for i in prisms])
    else:
        prism_list = f"{prisms[0].name}, {prisms[1].name}, {len(prisms) - 2} more..."

    emoji_prefix = str(user.emoji) + " " if user.emoji else ""

    if user.color:
        color = user.color
    else:
        color = "#6E593C"

    await refresh_quests(person)
    try:
        needed_xp = battle["seasons"][str(person.season)][person.battlepass]["xp"]
    except Exception:
        needed_xp = 1500

    stats = await gen_stats(person, "")
    highlighted_stat = None
    for stat in stats:
        if stat[0] == person.highlighted_stat:
            highlighted_stat = stat
            break
    if not highlighted_stat:
        for stat in stats:
            if stat[0] == "time_records":
                highlighted_stat = stat
                break

    embedVar = discord.Embed(
        title=f"{emoji_prefix}{person_id.name.replace('_', r'\_')}",
        description=f"{highlighted_stat[1]} {highlighted_stat[2]}\n{get_emoji('ach')} Achievements: {unlocked}/{total_achs}{minus_achs}\n⬆️ Cattlepass Level {person.battlepass} ({person.progress}/{needed_xp} XP)",
        color=discord.Colour.from_str(color),
    )

    debt = False
    give_collector = True
    total = 0
    valuenum = 0

    # for every cat
    cat_desc = ""
    for i in cattypes:
        icon = get_emoji(i.lower() + "cat")
        cat_num = person[f"cat_{i}"]
        if cat_num < 0:
            debt = True
        if cat_num != 0:
            total += cat_num
            valuenum += (sum(type_dict.values()) / type_dict[i]) * cat_num
            cat_desc += f"{icon} **{i}** {cat_num:,}\n"
        else:
            give_collector = False

    if user.custom:
        icon = get_emoji(str(user.user_id) + "cat")
        cat_desc += f"{icon} **{user.custom}** {user.custom_num:,}"

    if len(cat_desc) == 0:
        cat_desc = f"u hav no cats {get_emoji('cat_cry')}"

    if embedVar.description:
        embedVar.description += f"\n{get_emoji('staring_cat')} Cats: {total:,}, Value: {round(valuenum):,}\n{get_emoji('prism')} Prisms: {prism_list} ({prism_boost}%)\n\n{cat_desc}"

    if user.image.startswith("https://cdn.discordapp.com/attachments/"):
        embedVar.set_thumbnail(url=user.image)

    give_achs = []
    if me:
        # give some aches if we are vieweing our own inventory
        if len(news_list) > len(user.news_state.strip()) or "0" in user.news_state.strip()[-4:]:
            embedVar.set_author(name="You have unread news! /news")

        if give_collector:
            give_achs.append("collecter")

        if person.time <= 5:
            give_achs.append("fast_catcher")
        if person.timeslow >= 3600:
            give_achs.append("slow_catcher")

        if total >= 100:
            give_achs.append("second")
        if total >= 1000:
            give_achs.append("third")
        if total >= 10000:
            give_achs.append("fourth")

        if unlocked >= 15:
            give_achs.append("achiever")

        if debt:
            shared.bot.loop.create_task(debt_cutscene(message, person))

    return embedVar, give_achs


# ───────────────────────────────────────────────────────────────────────
#  /inventory
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="View your inventory")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="Person to view the inventory of!")
async def inventory(message: discord.Interaction, person_id: Optional[discord.User]):
    await message.response.defer()
    if not person_id:
        person_id = message.user
    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user = await User.get_or_create(user_id=message.user.id)
    stats = await gen_stats(person, "")

    async def edit_profile(interaction: discord.Interaction):
            if interaction.user.id != person_id.id:
                await do_funny(interaction)
                return

            def stat_select(category):
                options = [discord.SelectOption(emoji="⬅️", label="Back", value="back")]
                track = False
                for stat in stats:
                    if len(stat) == 2:
                        track = bool(stat[1] == category)
                    if len(stat) == 3 and track:
                        options.append(discord.SelectOption(value=stat[0], emoji=stat[1], label=stat[2]))

                select = discord.ui.Select(placeholder="Edit highlighted stat... (2/2)", options=options)

                async def select_callback(interaction: discord.Interaction):
                    await interaction.response.defer()
                    if select.values[0] == "back":
                        view = LayoutView(timeout=VIEW_TIMEOUT)
                        view.add_item(category_select())
                        await interaction.edit_original_response(view=view)
                    else:
                        # update the stat
                        person.highlighted_stat = select.values[0]
                        await person.save()
                        await interaction.edit_original_response(content="Highlighted stat updated!", embed=None, view=None)

                select.callback = select_callback
                return select

            def category_select():
                options = []
                for stat in stats:
                    if len(stat) != 2:
                        continue
                    options.append(discord.SelectOption(emoji=stat[0], label=stat[1], value=stat[1]))

                select = discord.ui.Select(placeholder="Edit highlighted stat... (1/2)", options=options)

                async def select_callback(interaction: discord.Interaction):
                    await interaction.response.defer()
                    view = LayoutView(timeout=VIEW_TIMEOUT)
                    view.add_item(stat_select(select.values[0]))
                    await interaction.edit_original_response(view=view)

                select.callback = select_callback
                return select

            highlighted_stat = None
            for stat in stats:
                if stat[0] == person.highlighted_stat:
                    highlighted_stat = stat
                    break
            if not highlighted_stat:
                for stat in stats:
                    if stat[0] == "time_records":
                        highlighted_stat = stat
                        break

            view = LayoutView(timeout=VIEW_TIMEOUT)
            view.add_item(category_select())

            is_supporter = user.premium or user.rain_minutes >= 10

            if is_supporter:
                if not user.color:
                    user.color = "#6E593C"
                profile_img = user.image if user.image.startswith("https://cdn.discordapp.com/attachments/") else None
                description = (
                    f"## {(user.emoji + ' ') if user.emoji else ''}Edit Profile\n"
                    "👑 __Supporter Settings__ *(global, change with `/editprofile`)*\n"
                    f"**Color**: {user.color.lower() if user.color.upper() not in ['', '#6E593C'] else 'Default'}\n"
                    f"**Emoji**: {user.emoji if user.emoji else 'None'}\n"
                    f"**Image**: {'Yes' if profile_img else 'No'}\n\n"
                    f"__Highlighted Stat__\n{highlighted_stat[1]} {highlighted_stat[2]}"
                )
                try:
                    accent = int(user.color.lstrip("#"), 16)
                except Exception:
                    accent = Colors.brown

                if profile_img:
                    container = Container(
                        Section(TextDisplay(description), Thumbnail(profile_img)),
                        accent_color=accent,
                    )
                else:
                    container = Container(description, accent_color=accent)
            else:
                description = (
                    "## Edit Profile\n"
                    "👑 __Supporter Settings__\n"
                    "👑 **Color** *(need 10 rain minutes or supporter)*\n"
                    "👑 **Emoji** *(need 10 rain minutes or supporter)*\n"
                    "👑 **Image** *(need 10 rain minutes or supporter)*\n\n"
                    f"__Highlighted Stat__\n{highlighted_stat[1]} {highlighted_stat[2]}"
                )
                container = Container(description, accent_color=Colors.brown)

            view.add_item(container)
            await interaction.response.send_message(view=view, ephemeral=True)

    embedVar, give_achs = await gen_inventory(message, person_id)

    embedVar.set_footer(text=rain_shill)

    if person_id.id == message.user.id:
        view = LayoutView(timeout=VIEW_TIMEOUT)
        btn = Button(emoji="📝", label="Edit", style=ButtonStyle.blurple)
        btn.callback = edit_profile
        view.add_item(btn)
        await message.followup.send(embed=embedVar, view=view)
    else:
        await message.followup.send(embed=embedVar)

    for ach in give_achs:
        await achemb(message, ach, "followup")


# ───────────────────────────────────────────────────────────────────────
#  /editprofile
# ───────────────────────────────────────────────────────────────────────

if config.DONOR_CHANNEL_ID:

    @shared.bot.tree.command(description="(SUPPORTER) Customize your profile!")
    @discord.app_commands.rename(provided_emoji="emoji")
    @discord.app_commands.describe(
        color="Color for your profile in hex form (e.g. #6E593C)",
        provided_emoji="A default Discord emoji to show near your username.",
        image="A square image to show in top-right corner of your profile.",
    )
    async def editprofile(
        message: discord.Interaction,
        color: Optional[str],
        provided_emoji: Optional[str],
        image: Optional[discord.Attachment],
    ):
        if not config.DONOR_CHANNEL_ID:
            return

        user = await User.get_or_create(user_id=message.user.id)
        if not user.premium and user.rain_minutes < 10:
            await message.response.send_message(
                "👑 This feature is supporter-only!\nBuy anything from cattito Store to unlock profile customization! (or earn 10+ rain minutes)"
            )
            return

        if provided_emoji and discord_emoji.to_discord(provided_emoji.strip(), get_all=False, put_colons=False):
            user.emoji = provided_emoji.strip()

        if color:
            match = re.search(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color)
            if match:
                user.color = match.group(0)
        if image and image.content_type in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
            # reupload image
            channeley = shared.bot.get_partial_messageable(config.DONOR_CHANNEL_ID)
            file = await image.to_file()
            if "." in file.filename:
                ext = file.filename[file.filename.rfind("."):]
                file.filename = "i" + ext
            else:
                file.filename = "i"
            msg = await channeley.send(file=file)
            user.image = msg.attachments[0].url
        await user.save()
        embedVar, _ = await gen_inventory(message, message.user)
        await message.response.send_message("Success! Here is a preview:", embed=embedVar)


# ───────────────────────────────────────────────────────────────────────
#  /packs
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="View and open packs")
async def packs(message: discord.Interaction):
    async def process_pack_opening(limit=None):
        await user.refresh_from_db()

        pack_names = [pack["name"] for pack in pack_data]
        total_pack_count = sum(user[f"pack_{pack_id.lower()}"] for pack_id in pack_names)

        if total_pack_count < 1:
            return None

        real_to_open = total_pack_count
        if limit:
            real_to_open = min(limit, total_pack_count)

        display_cats = real_to_open >= 50
        results_header = []
        results_detail = []
        results_percat = {cat: 0 for cat in cattypes}
        total_upgrades = 0
        opened_so_far = 0

        for level, pack in enumerate(pack_names):
            if opened_so_far >= real_to_open:
                break
            logging.debug("Opened pack %s", pack)
            pack_id = f"pack_{pack.lower()}"
            this_packs_count = user[pack_id]
            if this_packs_count < 1:
                continue

            opening_this = min(this_packs_count, real_to_open - opened_so_far)

            results_header.append(f"{opening_this:,}x {get_emoji(pack.lower() + 'pack')}")
            for _i in range(opening_this):
                chosen_type, cat_amount, upgrades, rewards = get_pack_rewards(level, is_single=False)
                total_upgrades += upgrades
                if not display_cats:
                    results_detail.append(rewards)
                results_percat[chosen_type] += cat_amount
                if _i % 100 == 0:
                    await asyncio.sleep(0)

            user[pack_id] -= opening_this
            opened_so_far += opening_this

        user.packs_opened += opened_so_far
        user.pack_upgrades += total_upgrades
        for cat_type, cat_amount in results_percat.items():
            user[f"cat_{cat_type}"] += cat_amount
        await user.save()

        final_header = f"Opened {opened_so_far:,} packs!"
        pack_list = "**" + ", ".join(results_header) + "**"
        final_result = "\n".join(results_detail)

        if display_cats or len(final_result) > 4000 - len(pack_list):
            cat_summary = []
            for cat in cattypes:
                if results_percat[cat] > 0:
                    cat_summary.append(f"{get_emoji(cat.lower() + 'cat')} x{results_percat[cat]:,}")
            final_result = "\n".join(cat_summary)

        if len(final_result) > 0:
            final_result = "\n\n" + final_result

        return discord.Embed(title=final_header, description=f"{pack_list}{final_result}", color=Colors.brown)

    async def open_custom_amount(interaction: discord.Interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        async def on_submit(interaction: discord.Interaction):
            try:
                amount = int(amount_input.value)
                if amount < 1:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message("Please enter a valid positive number!", ephemeral=True)
                return

            await interaction.response.defer()
            embed = await process_pack_opening(amount)
            if not embed:
                await interaction.followup.send("You have no packs!", ephemeral=True)
                return

            await message.edit_original_response(embed=embed, view=None)
            await asyncio.sleep(1)
            await message.edit_original_response(view=gen_view(user))

        modal = Modal(title="Open Custom Amount")
        amount_input = TextInput(label="Amount", placeholder="How many packs to open?", min_length=1, max_length=10)
        modal.add_item(amount_input)
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    async def confirm_open_all(interaction: discord.Interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        async def do_it(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()
            await open_all_packs(interaction)

        confirm_view = LayoutView(timeout=VIEW_TIMEOUT)
        yes_btn = Button(label="Yes, Open All", style=ButtonStyle.green)
        yes_btn.callback = do_it
        confirm_view.add_item(yes_btn)

        await interaction.response.send_message("Are you sure you want to open ALL your packs?", view=confirm_view, ephemeral=True)

    def gen_view(user):
        view = LayoutView(timeout=VIEW_TIMEOUT)
        empty = True
        total_amount = 0
        for pack in pack_data:
            if user[f"pack_{pack['name'].lower()}"] < 1:
                continue
            empty = False
            amount = user[f"pack_{pack['name'].lower()}"]
            total_amount += amount
            button = Button(
                emoji=get_emoji(pack["name"].lower() + "pack"),
                label=f"{pack['name']} ({amount:,})",
                style=ButtonStyle.blurple,
                custom_id=pack["name"],
            )
            button.callback = open_pack
            view.add_item(button)
        if empty:
            view.add_item(Button(label="No packs left!", disabled=True))
        if total_amount > 5:
            button = Button(label=f"Open all! ({total_amount:,})", style=ButtonStyle.gray)
            button.callback = confirm_open_all
            view.add_item(button)

            custom_btn = Button(label="Open Custom Amount...", style=ButtonStyle.gray)
            custom_btn.callback = open_custom_amount
            view.add_item(custom_btn)
        return view

    def get_pack_rewards(level: int, is_single=True):
        # returns cat_type, cat_amount, upgrades, verbal_output
        reward_texts = []
        build_string = ""
        upgrades = 0
        if not is_single:
            build_string = get_emoji(pack_data[level]["name"].lower() + "pack")

        bump_boost = 7 / 3 if level == 0 else 1

        # bump rarity
        while random.uniform(1, 100) <= pack_data[level]["upgrade"] * bump_boost:
            if is_single:
                reward_texts.append(f"{get_emoji(pack_data[level]['name'].lower() + 'pack')} {pack_data[level]['name']}\n" + build_string)
                build_string = f"Upgraded from {get_emoji(pack_data[level]['name'].lower() + 'pack')} {pack_data[level]['name']}!\n" + build_string
            else:
                build_string += f" -> {get_emoji(pack_data[level + 1]['name'].lower() + 'pack')}"
            level += 1
            upgrades += 1
        final_level = pack_data[level]
        if is_single:
            reward_texts.append(f"{get_emoji(final_level['name'].lower() + 'pack')} {final_level['name']}\n" + build_string)

        # select cat type
        goal_value = final_level["value"]
        chosen_type = random.choice(cattypes)
        cat_emoji = get_emoji(chosen_type.lower() + "cat")
        pre_cat_amount = goal_value / (sum(type_dict.values()) / type_dict[chosen_type])
        if pre_cat_amount % 1 > random.random():
            cat_amount = math.ceil(pre_cat_amount)
        else:
            cat_amount = math.floor(pre_cat_amount)
        if pre_cat_amount < 1:
            if is_single:
                reward_texts.append(
                    reward_texts[-1] + f"\n{round(pre_cat_amount * 100, 2)}% chance for a {get_emoji(chosen_type.lower() + 'cat')} {chosen_type} cat"
                )
                reward_texts.append(reward_texts[-1] + ".")
                reward_texts.append(reward_texts[-1] + ".")
                reward_texts.append(reward_texts[-1] + ".")
            else:
                build_string += f" {round(pre_cat_amount * 100, 2)}% {cat_emoji}? "
            if cat_amount == 1:
                # success
                if is_single:
                    reward_texts.append(reward_texts[-1] + "\n✅ Success!")
                else:
                    build_string += f"✅ -> {cat_emoji} 1"
            else:
                # fail
                if is_single:
                    reward_texts.append(reward_texts[-1] + "\n❌ Fail!")
                else:
                    build_string += f"❌ -> {get_emoji('finecat')} 1"
                chosen_type = "Fine"
                cat_amount = 1
        elif not is_single:
            build_string += f" {cat_emoji} {cat_amount:,}"
        if is_single:
            reward_texts.append(reward_texts[-1] + f"\nYou got {get_emoji(chosen_type.lower() + 'cat')} {cat_amount:,} {chosen_type} cats!")
            return chosen_type, cat_amount, upgrades, reward_texts
        return chosen_type, cat_amount, upgrades, build_string

    async def open_pack(interaction: discord.Interaction):
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        await interaction.response.defer()
        pack = interaction.data["custom_id"]
        await user.refresh_from_db()
        if user[f"pack_{pack.lower()}"] < 1:
            return
        level = next((i for i, p in enumerate(pack_data) if p["name"] == pack), 0)

        chosen_type, cat_amount, upgrades, reward_texts = get_pack_rewards(level)
        user[f"cat_{chosen_type}"] += cat_amount
        user.pack_upgrades += upgrades
        user.packs_opened += 1
        user[f"pack_{pack.lower()}"] -= 1
        await user.save()

        logging.debug("Opened pack %s", pack)

        embed = discord.Embed(title=reward_texts[0], color=Colors.brown)
        await interaction.edit_original_response(embed=embed, view=None)
        for reward_text in reward_texts[1:]:
            await asyncio.sleep(1)
            things = reward_text.split("\n", 1)
            embed = discord.Embed(title=things[0], description=things[1], color=Colors.brown)
            await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(1)
        await interaction.edit_original_response(view=gen_view(user))
        await progress(message, user, "pack_open")

    async def open_all_packs(interaction: discord.Interaction):
        embed = await process_pack_opening()
        if not embed:
            return

        await message.edit_original_response(embed=embed, view=None)
        await asyncio.sleep(1)
        await message.edit_original_response(view=gen_view(user))
        await progress(message, user, "pack_open")

    description = "Each pack starts at one of eight tiers of increasing value - Wooden, Stone, Bronze, Silver, Gold, Platinum, Diamond, or Celestial - and can repeatedly move up tiers with a 30% chance per upgrade. This means that even a pack starting at Wooden, through successive upgrades, can reach the Celestial tier.\n[Chance Info](<https://cattito.fun/>)\n\nClick the buttons below to start opening packs!"
    embed = discord.Embed(title=f"{get_emoji('bronzepack')} Packs", description=description, color=Colors.brown)
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await message.response.send_message(embed=embed, view=gen_view(user))


# ───────────────────────────────────────────────────────────────────────
#  /prism
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="cat prisms are a special power up")
@discord.app_commands.describe(person="Person to view the prisms of")
async def prism(message: discord.Interaction, person: Optional[discord.User]):
    icon = get_emoji("prism")
    page_number = 0

    if not person:
        person_id = message.user
    else:
        person_id = person

    user_prisms = await Prism.collect("guild_id = $1 AND user_id = $2", message.guild.id, person_id.id)
    all_prisms = await Prism.collect("guild_id = $1", message.guild.id)
    total_count = len(all_prisms)
    user_count = len(user_prisms)
    global_boost = 0.06 * math.log(2 * total_count + 1)
    user_boost = round((global_boost + 0.03 * math.log(2 * user_count + 1)) * 100, 3)
    prism_texts = []

    if person_id == message.user and user_count != 0:
        await achemb(message, "prism", "followup")

    order_map = {name: index for index, name in enumerate(prism_names)}
    prisms = all_prisms if not person else user_prisms
    prisms.sort(key=lambda p: order_map.get(p.name, float("inf")))

    for prism in prisms:
        prism_texts.append(f"{icon} **{prism.name}** {f'Owner: <@{prism.user_id}>' if not person else ''}\n<@{prism.creator}> crafted <t:{prism.time}:D>")

    if len(prisms) == 0:
        prism_texts.append("No prisms found!")

    async def confirm_craft(interaction: discord.Interaction):
        await interaction.response.defer()
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        # check we still can craft
        for i in cattypes:
            if user["cat_" + i] < 1:
                await interaction.followup.send("You don't have enough cats. Nice try though.", ephemeral=True)
                return

        if await Prism.count("guild_id = $1", interaction.guild.id) >= len(prism_names):
            await interaction.followup.send("This server has reached the prism limit.", ephemeral=True)
            return

        # determine the next name
        for selected_name in prism_names:
            if not await Prism.get_or_none(guild_id=message.guild.id, name=selected_name):
                break

        youngest_prism = await Prism.collect("guild_id = $1 ORDER BY time DESC LIMIT 1", message.guild.id)
        if youngest_prism:
            selected_time = max(round(time.time()), youngest_prism[0].time + 1)
        else:
            selected_time = round(time.time())

        # actually take away cats
        for i in cattypes:
            user["cat_" + i] -= 1
        await user.save()

        # create the prism
        await Prism.create(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            creator=interaction.user.id,
            time=selected_time,
            name=selected_name,
        )

        logging.debug("Created prism")

        await message.followup.send(f"{icon} {interaction.user.mention} has created prism {selected_name}!")
        await achemb(interaction, "prism", "followup")
        await achemb(interaction, "collecter", "followup")

    async def craft_prism(interaction: discord.Interaction):
        user = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)

        found_cats = await cats_in_server(interaction.guild.id)
        missing_cats = []
        for i in cattypes:
            if user[f"cat_{i}"] > 0:
                continue
            if i in found_cats:
                missing_cats.append(get_emoji(i.lower() + "cat"))
            else:
                missing_cats.append(get_emoji("mysterycat"))

        if len(missing_cats) == 0:
            view = LayoutView(timeout=VIEW_TIMEOUT)
            confirm_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
            confirm_button.callback = confirm_craft
            description = "The crafting recipe is __ONE of EVERY cat type__.\nContinue crafting?"
        else:
            view = LayoutView(timeout=VIEW_TIMEOUT)
            confirm_button = Button(label="Not enough cats!", style=ButtonStyle.red, disabled=True)
            description = "The crafting recipe is __ONE of EVERY cat type__.\nYou are missing " + "".join(missing_cats)

        view.add_item(confirm_button)
        await interaction.response.send_message(description, view=view, ephemeral=True)

    async def prev_page(interaction):
        nonlocal page_number
        page_number -= 1
        embed, view = gen_page()
        await interaction.response.edit_message(embed=embed, view=view)

    async def next_page(interaction):
        nonlocal page_number
        page_number += 1
        embed, view = gen_page()
        await interaction.response.edit_message(embed=embed, view=view)

    def gen_page():
        target = "" if not person else f"{person_id.name}'s"

        embed = discord.Embed(
            title=f"{icon} {target} Cat Prisms",
            color=Colors.brown,
            description="Prisms are a tradeable power-up which occasionally bumps cat rarity up by one. Each prism crafted gives the entire server an increased chance to get upgraded, plus additional chance for prism owner.\n\n",
        ).set_footer(
            text=f"{total_count} Total Prisms | Server boost: {round(global_boost * 100, 3)}%\n{person_id.name}'s prisms | Owned: {user_count} | Personal boost: {user_boost}%"
        )

        embed.description += "\n".join(prism_texts[page_number * 26 : (page_number + 1) * 26])

        view = LayoutView(timeout=VIEW_TIMEOUT)

        craft_button = Button(label="Craft!", style=ButtonStyle.blurple, emoji=icon)
        craft_button.callback = craft_prism
        view.add_item(craft_button)

        prev_button = Button(label="<-", disabled=bool(page_number == 0))
        prev_button.callback = prev_page
        view.add_item(prev_button)

        next_button = Button(label="->", disabled=bool(page_number == (len(prism_texts) + 1) // 26))
        next_button.callback = next_page
        view.add_item(next_button)

        return embed, view

    embed, view = gen_page()
    await message.response.send_message(embed=embed, view=view)


# ───────────────────────────────────────────────────────────────────────
#  /gift
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="give cats now")
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(
    person="Whom to gift?",
    cat_type="im gonna airstrike your house from orbit",
    amount="And how much?",
)
@discord.app_commands.autocomplete(cat_type=gift_autocomplete)
async def gift(
    message: discord.Interaction,
    person: discord.User,
    cat_type: str,
    amount: Optional[int],
):
    if amount is None:
        # default the amount to 1
        amount = 1
    person_id = person.id

    if amount <= 0 or message.user.id == person_id:
        # haha skill issue
        await message.response.send_message("no", ephemeral=True)
        if message.user.id == person_id:
            await achemb(message, "lonely", "followup")
        return

    if cat_type in cattypes:
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        # if we even have enough cats
        if user[f"cat_{cat_type}"] >= amount:
            reciever = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id)
            user[f"cat_{cat_type}"] -= amount
            reciever[f"cat_{cat_type}"] += amount
            try:
                user.cats_gifted += amount
                reciever.cat_gifts_recieved += amount
            except Exception:
                pass
            await user.save()
            await reciever.save()
            content = f"Successfully transfered {amount:,} {cat_type} cats from {message.user.mention} to <@{person_id}>!"

            # handle tax
            if amount >= 5:
                tax_amount = round(amount * 0.2)
                tax_debounce = False

                async def pay(interaction):
                    nonlocal tax_debounce
                    if interaction.user.id == message.user.id and not tax_debounce:
                        tax_debounce = True
                        await interaction.response.defer()
                        await user.refresh_from_db()
                        try:
                            # transfer tax
                            user[f"cat_{cat_type}"] -= tax_amount

                            try:
                                await interaction.edit_original_response(view=None)
                            except Exception:
                                pass
                            await interaction.followup.send(f"Tax of {tax_amount:,} {cat_type} cats was withdrawn from your account!")
                        finally:
                            # always save to prevent issue with exceptions leaving bugged state
                            await user.save()
                        await achemb(message, "good_citizen", "followup")
                        if user[f"cat_{cat_type}"] < 0:
                            shared.bot.loop.create_task(debt_cutscene(interaction, user))
                    else:
                        await do_funny(interaction)

                async def evade(interaction):
                    if interaction.user.id == message.user.id:
                        await interaction.response.defer()
                        try:
                            await interaction.edit_original_response(view=None)
                        except Exception:
                            pass
                        await interaction.followup.send(f"You evaded the tax of {tax_amount:,} {cat_type} cats.")
                        await achemb(message, "secret", "followup")
                    else:
                        await do_funny(interaction)

                button = Button(label="Pay 20% tax", style=ButtonStyle.green)
                button.callback = pay

                button2 = Button(label="Evade the tax", style=ButtonStyle.red)
                button2.callback = evade

                myview = LayoutView(timeout=VIEW_TIMEOUT)

                myview.add_item(button)
                myview.add_item(button2)

                await message.response.send_message(content, view=myview, allowed_mentions=discord.AllowedMentions(users=True))
            else:
                await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

            # handle aches
            await achemb(message, "donator", "followup")
            await achemb(message, "anti_donator", "followup", person)
            if person_id == shared.bot.user.id and cat_type == "Ultimate" and int(amount) >= 5:
                await achemb(message, "rich", "followup")
            if person_id == shared.bot.user.id:
                await achemb(message, "sacrifice", "followup")
            if cat_type == "Nice" and int(amount) == 69:
                await achemb(message, "nice", "followup")

            await progress(message, user, "gift")
        else:
            await message.response.send_message("no", ephemeral=True)
    elif cat_type.lower() == "rain":
        if person_id == shared.bot.user.id:
            await message.response.send_message("you can't sacrifice rains", ephemeral=True)
            return

        actual_user = await User.get_or_create(user_id=message.user.id)
        actual_receiver = await User.get_or_create(user_id=person_id)
        if actual_user.rain_minutes >= amount:
            actual_user.rain_minutes -= amount
            actual_receiver.rain_minutes += amount
            await actual_user.save()
            await actual_receiver.save()
            content = f"Successfully transfered {amount:,} minutes of rain from {message.user.mention} to <@{person_id}>!"

            await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

            # handle aches
            await achemb(message, "donator", "followup")
            await achemb(message, "anti_donator", "followup", person)
            user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
            await progress(message, user, "gift")

            # --- Rain grant log (gift) ---
            try:
                gift_rain_embed = discord.Embed(
                    title="☔ Rain Minutes Granted",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow(),
                )
                gift_rain_embed.add_field(name="Receiver", value=f"<@{person_id}> ({person_id})", inline=True)
                gift_rain_embed.add_field(name="Source", value=f"Gift from {message.user} ({message.user.id})", inline=True)
                gift_rain_embed.add_field(name="Minutes Added", value=str(amount), inline=True)
                gift_rain_embed.add_field(name="Receiver Total", value=str(actual_receiver.rain_minutes), inline=True)
                gift_rain_embed.add_field(name="Sender Remaining", value=str(actual_user.rain_minutes), inline=True)
                await log_rain(gift_rain_embed)
            except Exception as log_err:
                logging.warning(f"Rain gift log failed: {log_err}")
        else:
            await message.response.send_message("no", ephemeral=True)

        try:
            ch = shared.bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
            await ch.send(f"{message.user.id} gave {amount}m to {person_id}")
        except Exception:
            pass
    elif cat_type.lower() in [i["name"].lower() for i in pack_data]:
        cat_type = cat_type.lower()
        # packs um also this seems to be repetetive uh
        user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
        # if we even have enough packs
        if user[f"pack_{cat_type}"] >= amount:
            reciever = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id)
            user[f"pack_{cat_type}"] -= amount
            reciever[f"pack_{cat_type}"] += amount
            await user.save()
            await reciever.save()
            content = f"Successfully transfered {amount:,} {cat_type} packs from {message.user.mention} to <@{person_id}>!"

            await message.response.send_message(content, allowed_mentions=discord.AllowedMentions(users=True))

            # handle aches
            await achemb(message, "donator", "followup")
            await achemb(message, "anti_donator", "followup", person)
            if person_id == shared.bot.user.id:
                await achemb(message, "sacrifice", "followup")

            await progress(message, user, "gift")
        else:
            await message.response.send_message("no", ephemeral=True)
    else:
        await message.response.send_message("bro what", ephemeral=True)


# ───────────────────────────────────────────────────────────────────────
#  /trade
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="Trade stuff!")
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="why would you need description")
async def trade(message: discord.Interaction, person_id: discord.User):
    person1 = message.user
    person2 = person_id

    blackhole = False

    person1accept = False
    person2accept = False

    person1value = 0
    person2value = 0

    person1gives = {}
    person2gives = {}

    user1 = await Profile.get_or_create(guild_id=message.guild.id, user_id=person1.id)
    user2 = await Profile.get_or_create(guild_id=message.guild.id, user_id=person2.id)

    if not shared.bot.user:
        return

    # do the funny
    if person2.id == shared.bot.user.id:
        person2gives["eGirl"] = 9999999

    # this is the deny button code
    async def denyb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        await interaction.response.defer()
        blackhole = True
        person1gives = {}
        person2gives = {}
        try:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention} has cancelled the trade.",
                embed=None,
                view=None,
            )
        except Exception:
            pass

    # this is the accept button code
    async def acceptb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, person1value, person2value, user1, user2, blackhole
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        # clicking accept again would make you un-accept
        if interaction.user == person1:
            person1accept = not person1accept
        elif interaction.user == person2:
            person2accept = not person2accept

        await interaction.response.defer()
        await update_trade_embed(interaction)

        if person1accept and person2 == shared.bot.user:
            await achemb(message, "desperate", "followup")

        if blackhole:
            await update_trade_embed(interaction)
            return

        if person1accept and person2accept:
            blackhole = True
            await user1.refresh_from_db()
            await user2.refresh_from_db()
            actual_user1 = await User.get_or_create(user_id=person1.id)
            actual_user2 = await User.get_or_create(user_id=person2.id)

            # check if we have enough things (person could have moved them during the trade)
            error = False
            person1prismgive = 0
            person2prismgive = 0
            for k, v in person1gives.items():
                if k in prism_names:
                    person1prismgive += 1
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=k)
                    if not prism or prism.user_id != person1.id:
                        error = True
                        break
                    continue
                elif k == "rains":
                    if actual_user1.rain_minutes < v:
                        error = True
                        break
                elif k in cattypes:
                    if user1[f"cat_{k}"] < v:
                        error = True
                        break
                elif user1[f"pack_{k.lower()}"] < v:
                    error = True
                    break

            for k, v in person2gives.items():
                if k in prism_names:
                    person2prismgive += 1
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=k)
                    if not prism or prism.user_id != person2.id:
                        error = True
                        break
                    continue
                elif k == "rains":
                    if actual_user2.rain_minutes < v:
                        error = True
                        break
                elif k in cattypes:
                    if user2[f"cat_{k}"] < v:
                        error = True
                        break
                elif user2[f"pack_{k.lower()}"] < v:
                    error = True
                    break

            if error:
                try:
                    await interaction.edit_original_response(
                        content="Uh oh - some of the cats/prisms/packs/rains disappeared while trade was happening",
                        embed=None,
                        view=None,
                    )
                except Exception:
                    await interaction.followup.send("Uh oh - some of the cats/prisms/packs/rains disappeared while trade was happening")
                return

            # exchange
            cat_count = 0
            for k, v in person1gives.items():
                if k in prism_names:
                    move_prism = await Prism.get_or_none(guild_id=message.guild.id, name=k)
                    move_prism.user_id = person2.id
                    await move_prism.save()
                elif k == "rains":
                    actual_user1.rain_minutes -= v
                    actual_user2.rain_minutes += v
                    try:
                        ch = shared.bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
                        await ch.send(f"{actual_user1.user_id} traded {v}m to {actual_user2.user_id}")
                    except Exception:
                        pass
                elif k in cattypes:
                    cat_count += v
                    user1[f"cat_{k}"] -= v
                    user2[f"cat_{k}"] += v
                else:
                    user1[f"pack_{k.lower()}"] -= v
                    user2[f"pack_{k.lower()}"] += v

            for k, v in person2gives.items():
                if k in prism_names:
                    move_prism = await Prism.get_or_none(guild_id=message.guild.id, name=k)
                    move_prism.user_id = person1.id
                    await move_prism.save()
                elif k == "rains":
                    actual_user2.rain_minutes -= v
                    actual_user1.rain_minutes += v
                    try:
                        ch = shared.bot.get_partial_messageable(config.RAIN_CHANNEL_ID)
                        await ch.send(f"{actual_user2.user_id} traded {v}m to {actual_user1.user_id}")
                    except Exception:
                        pass
                elif k in cattypes:
                    cat_count += v
                    user1[f"cat_{k}"] += v
                    user2[f"cat_{k}"] -= v
                else:
                    user1[f"pack_{k.lower()}"] += v
                    user2[f"pack_{k.lower()}"] -= v

            user1.cats_traded += cat_count
            user2.cats_traded += cat_count
            user1.trades_completed += 1
            user2.trades_completed += 1

            await user1.save()
            await user2.save()
            await actual_user1.save()
            await actual_user2.save()

            # --- Rain grant log (trade) ---
            try:
                rain_in_trade = False
                if "rains" in person1gives:
                    trade_rain_embed = discord.Embed(title="☔ Rain Minutes Granted", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                    trade_rain_embed.add_field(name="Receiver", value=f"<@{person2.id}> ({person2.id})", inline=True)
                    trade_rain_embed.add_field(name="Source", value=f"Trade from {person1} ({person1.id})", inline=True)
                    trade_rain_embed.add_field(name="Minutes Added", value=str(person1gives["rains"]), inline=True)
                    trade_rain_embed.add_field(name="Receiver Total", value=str(actual_user2.rain_minutes), inline=True)
                    await log_rain(trade_rain_embed)
                    rain_in_trade = True
                if "rains" in person2gives:
                    trade_rain_embed2 = discord.Embed(title="☔ Rain Minutes Granted", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                    trade_rain_embed2.add_field(name="Receiver", value=f"<@{person1.id}> ({person1.id})", inline=True)
                    trade_rain_embed2.add_field(name="Source", value=f"Trade from {person2} ({person2.id})", inline=True)
                    trade_rain_embed2.add_field(name="Minutes Added", value=str(person2gives["rains"]), inline=True)
                    trade_rain_embed2.add_field(name="Receiver Total", value=str(actual_user1.rain_minutes), inline=True)
                    await log_rain(trade_rain_embed2)
            except Exception as log_err:
                logging.warning(f"Trade rain log failed: {log_err}")

            try:
                await interaction.edit_original_response(content="Trade finished!", view=None)
            except Exception:
                await interaction.followup.send()

            await achemb(message, "extrovert", "followup")
            await achemb(message, "extrovert", "followup", person2)

            if cat_count >= 1000:
                await achemb(message, "capitalism", "followup")
                await achemb(message, "capitalism", "followup", person2)

            if person2value + person1value == 0:
                await achemb(message, "absolutely_nothing", "followup")
                await achemb(message, "absolutely_nothing", "followup", person2)

            if person2value - person1value >= 100:
                await achemb(message, "profit", "followup")
            if person1value - person2value >= 100:
                await achemb(message, "profit", "followup", person2)

            if person1value > person2value:
                await achemb(message, "scammed", "followup")
            if person2value > person1value:
                await achemb(message, "scammed", "followup", person2)

            if person1value == person2value and person1gives != person2gives:
                await achemb(message, "perfectly_balanced", "followup")
                await achemb(message, "perfectly_balanced", "followup", person2)

            await progress(message, user1, "trade")
            await progress(message, user2, "trade")

    # add cat code
    async def addb(interaction):
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
        if interaction.user != person1 and interaction.user != person2:
            await do_funny(interaction)
            return

        currentuser = 1 if interaction.user == person1 else 2

        # all we really do is spawn the modal
        modal = TradeModal(currentuser)
        await interaction.response.send_modal(modal)

    # this is ran like everywhere when you do anything
    # it updates the embed
    async def gen_embed():
        nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives, blackhole, person1value, person2value

        if blackhole:
            # no way thats fun
            await achemb(message, "blackhole", "followup")
            await achemb(message, "blackhole", "followup", person2)
            return discord.Embed(color=Colors.brown, title="Blackhole", description="How Did We Get Here?"), None

        view = LayoutView(timeout=VIEW_TIMEOUT)

        accept = Button(label="Accept", style=ButtonStyle.green)
        accept.callback = acceptb

        deny = Button(label="Deny", style=ButtonStyle.red)
        deny.callback = denyb

        add = Button(label="Offer...", style=ButtonStyle.blurple)
        add.callback = addb

        view.add_item(accept)
        view.add_item(deny)
        view.add_item(add)

        person1name = person1.name.replace("_", "\\_")
        person2name = person2.name.replace("_", "\\_")
        coolembed = discord.Embed(
            color=Colors.brown,
            title=f"{person1name} and {person2name} trade",
            description="no way",
        )

        # a single field for one person
        def field(personaccept, persongives, person, number):
            nonlocal coolembed, person1value, person2value
            icon = "⬜"
            if personaccept:
                icon = "✅"
            valuestr = ""
            valuenum = 0
            total = 0
            for k, v in persongives.items():
                if v == 0:
                    continue
                if k in prism_names:
                    # prisms
                    valuestr += f"{get_emoji('prism')} {k}\n"
                    for v2 in type_dict.values():
                        valuenum += sum(type_dict.values()) / v2
                elif k == "rains":
                    # rains
                    valuestr += f"☔ {v:,}m of Cat Rains\n"
                    valuenum += 900 * v
                elif k in cattypes:
                    # cats
                    valuenum += (sum(type_dict.values()) / type_dict[k]) * v
                    total += v
                    aicon = get_emoji(k.lower() + "cat")
                    valuestr += f"{aicon} {k} {v:,}\n"
                else:
                    # packs
                    valuenum += sum([i["totalvalue"] if i["name"] == k else 0 for i in pack_data]) * v
                    aicon = get_emoji(k.lower() + "pack")
                    valuestr += f"{aicon} {k} {v:,}\n"
            if not valuestr:
                valuestr = "Nothing offered!"
            else:
                valuestr += f"*Total value: {round(valuenum):,}\nTotal cats: {round(total):,}*"
                if number == 1:
                    person1value = round(valuenum)
                else:
                    person2value = round(valuenum)
            personname = person.name.replace("_", "\\_")
            coolembed.add_field(name=f"{icon} {personname}", inline=True, value=valuestr)

        field(person1accept, person1gives, person1, 1)
        field(person2accept, person2gives, person2, 2)

        return coolembed, view

    # this is wrapper around gen_embed() to edit the mesage automatically
    async def update_trade_embed(interaction):
        embed, view = await gen_embed()
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            await achemb(message, "blackhole", "followup")
            await achemb(message, "blackhole", "followup", person2)

    # lets go add cats modal thats fun
    class TradeModal(Modal):
        def __init__(self, currentuser):
            super().__init__(
                title="Add to the trade",
                timeout=3600,
            )
            self.currentuser = currentuser

            self.cattype = TextInput(
                label='Cat or Pack Type, Prism Name or "Rain"',
                placeholder="Fine / Wooden / Alpha / Rain",
            )
            self.add_item(self.cattype)

            self.amount = TextInput(label="Amount to offer", placeholder="1", required=False)
            self.add_item(self.amount)

        # this is ran when user submits
        async def on_submit(self, interaction: discord.Interaction):
            nonlocal person1, person2, person1accept, person2accept, person1gives, person2gives
            value = self.amount.value if self.amount.value else 1
            await user1.refresh_from_db()
            await user2.refresh_from_db()

            try:
                if int(value) < 0:
                    person1accept = False
                    person2accept = False
            except Exception:
                await interaction.response.send_message("invalid amount", ephemeral=True)
                return

            # handle prisms
            if (pname := " ".join(i.capitalize() for i in self.cattype.value.split())) in prism_names:
                try:
                    prism = await Prism.get_or_none(guild_id=interaction.guild.id, name=pname)
                    if not prism:
                        raise Exception
                except Exception:
                    await interaction.response.send_message("this prism doesnt exist", ephemeral=True)
                    return
                if prism.user_id != interaction.user.id:
                    await interaction.response.send_message("this is not your prism", ephemeral=True)
                    return
                if (self.currentuser == 1 and pname in person1gives.keys()) or (self.currentuser == 2 and pname in person2gives.keys()):
                    await interaction.response.send_message("you already added this prism", ephemeral=True)
                    return

                if self.currentuser == 1:
                    person1gives[pname] = 1
                else:
                    person2gives[pname] = 1
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            # handle packs
            if self.cattype.value.capitalize() in [i["name"] for i in pack_data]:
                pname = self.cattype.value.capitalize()
                if self.currentuser == 1:
                    if user1[f"pack_{pname.lower()}"] < int(value):
                        await interaction.response.send_message("you dont have enough packs", ephemeral=True)
                        return
                    new_val = person1gives.get(pname, 0) + int(value)
                    if new_val >= 0:
                        person1gives[pname] = new_val
                    else:
                        await interaction.response.send_message("skibidi toilet", ephemeral=True)
                        return
                else:
                    if user2[f"pack_{pname.lower()}"] < int(value):
                        await interaction.response.send_message("you dont have enough packs", ephemeral=True)
                        return
                    new_val = person2gives.get(pname, 0) + int(value)
                    if new_val >= 0:
                        person2gives[pname] = new_val
                    else:
                        await interaction.response.send_message("skibidi toilet", ephemeral=True)
                        return
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            # handle rains
            if "rain" in self.cattype.value.lower():
                user = await User.get_or_create(user_id=interaction.user.id)
                try:
                    if user.rain_minutes < int(value) or int(value) < 1:
                        await interaction.response.send_message("you dont have enough rains", ephemeral=True)
                        return
                except Exception:
                    await interaction.response.send_message("please enter a number for amount", ephemeral=True)
                    return

                if self.currentuser == 1:
                    try:
                        person1gives["rains"] += int(value)
                    except Exception:
                        person1gives["rains"] = int(value)
                else:
                    try:
                        person2gives["rains"] += int(value)
                    except Exception:
                        person2gives["rains"] = int(value)
                await interaction.response.defer()
                await update_trade_embed(interaction)
                return

            lc_input = self.cattype.value.lower()

            # loop through the cat types and find the correct one using lowercased user input.
            cname = cattype_lc_dict.get(lc_input, None)

            # if no cat type was found, the user input was invalid. as cname is still `None`
            if cname is None:
                await interaction.response.send_message("add a valid cat/pack/prism name 💀💀💀", ephemeral=True)
                return

            try:
                if self.currentuser == 1:
                    if user1[f"cat_{cname}"] < int(value):
                        await interaction.response.send_message("you dont have enough cats", ephemeral=True)
                        return
                    new_val = person1gives.get(cname, 0) + int(value)
                    if new_val >= 0:
                        person1gives[cname] = new_val
                    else:
                        await interaction.response.send_message("skibidi toilet", ephemeral=True)
                        return
                else:
                    if user2[f"cat_{cname}"] < int(value):
                        await interaction.response.send_message("you dont have enough cats", ephemeral=True)
                        return
                    new_val = person2gives.get(cname, 0) + int(value)
                    if new_val >= 0:
                        person2gives[cname] = new_val
                    else:
                        await interaction.response.send_message("skibidi toilet", ephemeral=True)
                        return
                await interaction.response.defer()
                await update_trade_embed(interaction)
            except Exception:
                await interaction.response.send_message("invalid amount", ephemeral=True)
                return

    embed, view = await gen_embed()
    await message.response.send_message(embed=embed, view=view)


# ───────────────────────────────────────────────────────────────────────
#  /rainshop
# ───────────────────────────────────────────────────────────────────────

@shared.bot.tree.command(description="Buy cat rains with cats! (very expensive) - Batch buying available")
async def rainshop(message: discord.Interaction):
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    rain_prices = {
        "Fine": 3000,
        "Snacc": 2800,
        "Nice": 2500,
        "Good": 2200,
        "Rare": 1800,
        "Wild": 1500,
        "Kittuh": 1200,
        "Baby": 1000,
        "Epic": 800,
        "Sus": 700,
        "Water": 650,
        "Brave": 600,
        "Unknown": 580,
        "Rickroll": 550,
        "Reverse": 500,
        "Superior": 450,
        "Trash": 400,
        "Legendary": 350,
        "Bloodmoon": 300,
        "Mythic": 280,
        "8bit": 260,
        "Corrupt": 240,
        "Professor": 220,
        "Divine": 200,
        "Space": 180,
        "Real": 160,
        "Ultimate": 140,
        "eGirl": 120,
        "eBoy": 100,
    }

    # Calculate total affordable rain across all cat types
    total_affordable_rain = 0
    affordable_breakdown = {}

    for cat_type, cost in rain_prices.items():
        user_amount = user[f"cat_{cat_type}"]
        affordable = user_amount // cost
        total_affordable_rain += affordable
        if affordable > 0:
            affordable_breakdown[cat_type] = affordable

    # Build affordability breakdown text
    if affordable_breakdown:
        breakdown_lines = []
        for cat_type, amount in sorted(affordable_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]:
            icon = get_emoji(cat_type.lower() + "cat")
            breakdown_lines.append(f"{icon} {cat_type}: {amount:,}m")
        if len(affordable_breakdown) > 10:
            breakdown_lines.append(f"… and {len(affordable_breakdown) - 10} more cat types")
        breakdown_text = "\n".join(breakdown_lines)
    else:
        breakdown_text = "You don't have any cats yet!"

    # Create dropdown select for all cat types (Discord limits selects to 25 options)
    cat_type_options = []
    for cat_type in list(rain_prices.keys())[:25]:
        cat_type_options.append(
            discord.SelectOption(
                label=cat_type,
                value=cat_type,
                emoji=get_emoji(cat_type.lower() + "cat")
            )
        )

    class SingleTypePurchaseModal(discord.ui.Modal):
        def __init__(self, cat_type, cost_per_minute):
            super().__init__(title=f"Buy Rain with {cat_type}", timeout=3600)
            self.cat_type = cat_type
            self.cost_per_minute = cost_per_minute
            self.minutes_input = discord.ui.TextInput(
                label="How many minutes of rain?",
                placeholder="e.g., 10",
                min_length=1,
                max_length=5,
                required=True,
            )
            self.add_item(self.minutes_input)

        async def on_submit(self, modal_interaction: discord.Interaction):
            try:
                minutes_requested = int(self.minutes_input.value)
                if minutes_requested < 1:
                    await modal_interaction.response.send_message("You must buy at least 1 minute!", ephemeral=True)
                    return
                if minutes_requested > 10000:
                    await modal_interaction.response.send_message("Maximum is 10,000 minutes per transaction.", ephemeral=True)
                    return
            except ValueError:
                await modal_interaction.response.send_message("Please enter a valid number!", ephemeral=True)
                return

            await modal_interaction.response.defer()
            await user.refresh_from_db()

            total_cost = minutes_requested * self.cost_per_minute
            if user[f"cat_{self.cat_type}"] < total_cost:
                needed = total_cost - user[f"cat_{self.cat_type}"]
                await modal_interaction.followup.send(
                    f"You don't have enough {self.cat_type} cats!\n"
                    f"You need {needed:,} more. Have: {user[f'cat_{self.cat_type}']:,} | Need: {total_cost:,}",
                    ephemeral=True,
                )
                return

            user[f"cat_{self.cat_type}"] -= total_cost
            user.rain_minutes_bought += minutes_requested
            global_user = await User.get_or_create(user_id=modal_interaction.user.id)
            global_user.rain_minutes += minutes_requested
            await user.save()
            await global_user.save()

            try:
                shop_rain_embed = discord.Embed(
                    title="☔ Rain Minutes Granted",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow(),
                )
                shop_rain_embed.add_field(name="User", value=f"{modal_interaction.user} ({modal_interaction.user.id})", inline=True)
                shop_rain_embed.add_field(name="Source", value=f"Rainshop ({self.cat_type})", inline=True)
                shop_rain_embed.add_field(name="Minutes Added", value=str(minutes_requested), inline=True)
                shop_rain_embed.add_field(name="Cost", value=f"{total_cost:,} {self.cat_type} cats", inline=True)
                shop_rain_embed.add_field(name="Total Rain Minutes", value=str(global_user.rain_minutes), inline=True)
                await log_rain(shop_rain_embed)
            except Exception as log_err:
                logging.warning(f"Rainshop single log failed: {log_err}")

            icon = get_emoji(self.cat_type.lower() + "cat")
            success_view = LayoutView(timeout=VIEW_TIMEOUT)
            success_view.add_item(Container(
                "## ✅ Purchase Successful!",
                f"You traded **{total_cost:,}** {icon} {self.cat_type} cats for **{minutes_requested}** rain minutes!\n\n"
                f"🌧️ Rain Minutes: **{global_user.rain_minutes:,}**\n"
                f"{icon} {self.cat_type} Cats: **{user[f'cat_{self.cat_type}']:,}**\n\n"
                "-# Use /rain to start a cat rain!",
                accent_color=Colors.green,
            ))
            await modal_interaction.followup.send(view=success_view)
            logging.debug("User %d bought %d rain minutes for %d %s cats (single type)", user.user_id, minutes_requested, total_cost, self.cat_type)

    class BatchPurchaseModal(discord.ui.Modal):
        def __init__(self, prices, profile):
            super().__init__(title="Batch Buy Rain", timeout=3600)
            self.prices = prices
            self.profile = profile
            self.minutes_input = discord.ui.TextInput(
                label="Total minutes of rain to buy",
                placeholder="e.g., 50",
                min_length=1,
                max_length=5,
                required=True,
            )
            self.add_item(self.minutes_input)
            self.cat_list_input = discord.ui.TextInput(
                label="Cats to spend (Cat1:amount Cat2:amount)",
                placeholder="e.g., Fine:100 Rare:50 Ultimate:10",
                min_length=1,
                max_length=500,
                required=True,
                style=discord.TextStyle.long,
            )
            self.add_item(self.cat_list_input)

        async def on_submit(self, modal_interaction: discord.Interaction):
            try:
                minutes_requested = int(self.minutes_input.value)
                if minutes_requested < 1:
                    await modal_interaction.response.send_message("You must buy at least 1 minute!", ephemeral=True)
                    return
                if minutes_requested > 10000:
                    await modal_interaction.response.send_message("Maximum is 10,000 minutes per transaction.", ephemeral=True)
                    return
            except ValueError:
                await modal_interaction.response.send_message("Please enter a valid number for minutes!", ephemeral=True)
                return

            cat_allocations = {}
            try:
                for entry in self.cat_list_input.value.split():
                    if ":" not in entry:
                        await modal_interaction.response.send_message(
                            "Invalid format! Use: `Cat1:amount Cat2:amount`\nExample: `Fine:100 Rare:50`",
                            ephemeral=True,
                        )
                        return
                    cat_name, amount_str = entry.split(":", 1)
                    amount = int(amount_str)
                    if amount < 0:
                        await modal_interaction.response.send_message("Amounts must be positive!", ephemeral=True)
                        return
                    matching_cat = next((ct for ct in self.prices if ct.lower() == cat_name.lower()), None)
                    if not matching_cat:
                        await modal_interaction.response.send_message(
                            f"Unknown cat type: `{cat_name}`\nValid types: {', '.join(sorted(self.prices))}",
                            ephemeral=True,
                        )
                        return
                    cat_allocations[matching_cat] = amount
            except ValueError:
                await modal_interaction.response.send_message("Invalid format! Make sure amounts are numbers.", ephemeral=True)
                return

            if not cat_allocations:
                await modal_interaction.response.send_message("You must specify at least one cat type!", ephemeral=True)
                return

            await modal_interaction.response.defer()
            await user.refresh_from_db()

            total_cost = 0
            cost_breakdown = {}
            for cat_type, amount in cat_allocations.items():
                cost = amount * self.prices[cat_type]
                total_cost += cost
                cost_breakdown[cat_type] = (amount, cost)

            for cat_type, (amount, _) in cost_breakdown.items():
                if user[f"cat_{cat_type}"] < amount:
                    shortage = amount - user[f"cat_{cat_type}"]
                    await modal_interaction.followup.send(
                        f"❌ Not enough {cat_type} cats! Need: {amount:,} | Have: {user[f'cat_{cat_type}']:,} | Short: {shortage:,}",
                        ephemeral=True,
                    )
                    return

            for cat_type, amount in cat_allocations.items():
                user[f"cat_{cat_type}"] -= amount
            user.rain_minutes_bought += minutes_requested
            global_user = await User.get_or_create(user_id=modal_interaction.user.id)
            global_user.rain_minutes += minutes_requested
            await user.save()
            await global_user.save()

            try:
                batch_rain_embed = discord.Embed(
                    title="☔ Rain Minutes Granted",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow(),
                )
                batch_rain_embed.add_field(name="User", value=f"{modal_interaction.user} ({modal_interaction.user.id})", inline=True)
                batch_rain_embed.add_field(name="Source", value="Rainshop (Batch)", inline=True)
                batch_rain_embed.add_field(name="Minutes Added", value=str(minutes_requested), inline=True)
                batch_rain_embed.add_field(name="Total Rain Minutes", value=str(global_user.rain_minutes), inline=True)
                await log_rain(batch_rain_embed)
            except Exception as log_err:
                logging.warning(f"Rainshop batch log failed: {log_err}")

            breakdown_lines = []
            for cat_type, (amount, cost) in sorted(cost_breakdown.items(), key=lambda x: x[1][1], reverse=True):
                icon = get_emoji(cat_type.lower() + "cat")
                breakdown_lines.append(f"{icon} {cat_type}: {amount:,} cats → {cost:,} cost")

            success_view = LayoutView(timeout=VIEW_TIMEOUT)
            success_view.add_item(Container(
                "## ✅ Batch Purchase Successful!",
                f"You traded **{total_cost:,}** cats for **{minutes_requested}** rain minutes!\n\n"
                + "\n".join(breakdown_lines)
                + f"\n\n🌧️ New Rain Balance: **{global_user.rain_minutes:,}**\n\n"
                "-# Use /rain to start a cat rain!",
                accent_color=Colors.green,
            ))
            await modal_interaction.followup.send(view=success_view)
            logging.debug("User %d batch bought %d rain minutes for %d total cats", user.user_id, minutes_requested, total_cost)

    async def single_type_purchase(interaction: discord.Interaction):
        cat_type = interaction.values[0]
        await interaction.response.send_modal(SingleTypePurchaseModal(cat_type, rain_prices[cat_type]))

    async def batch_purchase(interaction: discord.Interaction):
        await interaction.response.send_modal(BatchPurchaseModal(rain_prices, user))

    cat_select = discord.ui.Select(
        placeholder="💧 Select a cat type to sell",
        options=cat_type_options,
        custom_id="cat_type_select",
    )
    cat_select.callback = single_type_purchase

    batch_button = discord.ui.Button(
        label="🎯 Batch Buy (Mix & Match)",
        style=discord.ButtonStyle.success,
    )
    batch_button.callback = batch_purchase

    view = discord.ui.LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(Container(
        "## 💧 Cat Rain Shop",
        f"Convert your cats into precious rain minutes!\n\n**Total Rain You Can Afford: {total_affordable_rain:,} minutes**",
        "===",
        f"**📊 What You Can Afford**\n{breakdown_text}",
        "===",
        "**💡 How It Works**\n"
        "• **Single Type**: Buy rain using only one cat type (select below)\n"
        "• **Batch Buy**: Mix and match cats to get the best deal\n"
        "• More rare cats = better rates!",
        "===",
        "⚠️ All transactions are **permanent** and cannot be undone.",
        "===",
        ActionRow(cat_select),
        ActionRow(batch_button),
        accent_color=Colors.brown,
    ))

    await message.response.send_message(view=view)
