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

import asyncio, datetime, logging, random, time, math
from typing import Optional
import aiohttp
import discord
from discord.ui import TextDisplay, Section, Thumbnail, Container, LayoutView
import config
import shared
from shared import bot, emojis
from constants import (cattypes, type_dict, pack_data, prism_names, ach_list, ach_names,
    ach_titles, battle, news_list, VIEW_TIMEOUT, EXTRA_QUEST_TRIGGERS, catnip_list)
from core.colors import Colors
from core.utils import get_emoji, get_streak_reward
from database import Profile, User, Prism

NOXX_ID = 1370898570403647528


async def _post_webhook(webhook_url: str, embed: discord.Embed):
    """POST an embed to a Discord webhook URL."""
    payload = {"embeds": [embed.to_dict()]}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                logging.warning(f"Webhook post returned {resp.status}: {text[:200]}")


async def log_rain(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_RAIN", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_rain webhook failed: {e}")


async def get_xp_bonuses(profile, global_user, guild, prisms_crafted: int) -> list:
    bonuses = []

    # 1. Noxx in the server (+50%)
    noxx_here = guild is not None and guild.get_member(NOXX_ID) is not None
    bonuses.append({
        "mult":   1.5,
        "label":  "Noxx Neighbour",
        "emoji":  "🤝",
        "desc":   "Add Noxx to this server",
        "active": noxx_here,
    })

    # 2. Vote streak ≥ 7 days (+10%)
    streak = getattr(global_user, "vote_streak", 0) or 0
    bonuses.append({
        "mult":   1.1,
        "label":  "Loyal Voter",
        "emoji":  "🗳️",
        "desc":   f"Maintain a 7-day vote streak ({streak}/7)",
        "active": streak >= 7,
    })

    # 3. 50 quests completed in this server (+10%)
    quests = getattr(profile, "quests_completed", 0) or 0
    bonuses.append({
        "mult":   1.1,
        "label":  "Quest Grinder",
        "emoji":  "📜",
        "desc":   f"Complete 50 quests in this server ({quests}/50)",
        "active": quests >= 50,
    })

    # 4. Own a prism in this server (+10%)
    bonuses.append({
        "mult":   1.1,
        "label":  "Prism Holder",
        "emoji":  get_emoji("prism"),
        "desc":   f"Craft at least 1 prism in this server ({prisms_crafted}/1)",
        "active": prisms_crafted >= 1,
    })

    # 5. 500 total catches in this server (+10%)
    catches = getattr(profile, "total_catches", 0) or 0
    bonuses.append({
        "mult":   1.1,
        "label":  "Serial Catcher",
        "emoji":  "🐾",
        "desc":   f"Catch 500 cats in this server ({catches}/500)",
        "active": catches >= 500,
    })

    # 6. Battlepass level 20+ this season (+10%)
    bp_level = getattr(profile, "battlepass", 0) or 0
    bonuses.append({
        "mult":   1.1,
        "label":  "Battlepass Beast",
        "emoji":  "⭐",
        "desc":   f"Reach battlepass level 20 this season ({bp_level}/20)",
        "active": bp_level >= 20,
    })

    return bonuses


def compute_xp_multiplier(bonuses: list) -> float:
    total = 1.0
    for b in bonuses:
        if b["active"]:
            total *= b["mult"]
    return min(round(total, 4), 1.95)


async def achemb(message, ach_id, send_type, author_string=None):
    if not author_string:
        try:
            author_string = message.author
        except Exception:
            author_string = message.user
    author = author_string.id

    if not message.guild:
        return

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=author)

    if profile[ach_id]:
        return

    profile[ach_id] = True
    await profile.save()
    logging.debug("Achievement unlocked: %s", ach_id)
    ach_data = ach_list[ach_id]
    desc = ach_data["description"]
    if ach_id == "dataminer":
        desc = "Your head hurts -- you seem to have forgotten what you just did to get this."

    ach_flags = discord.MessageFlags(components_v2=True)

    if ach_id != "thanksforplaying":
        container = Container(
            Section(
                TextDisplay(f"## 🏆 Achievement get!\n### {ach_data['title']}\n{desc}"),
                Thumbnail("https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/ach.png"),
            ),
            TextDisplay(f"-# Unlocked by {author_string.name}"),
            accent_color=Colors.green,
        )
        view = LayoutView()
        view.add_item(container)
    else:
        container = Container(
            Section(
                TextDisplay(f"## 🌟 Demonic achievement unlocked!\n### Catnip Addict\nUncover the mafia's truth\nThanks for playing! ✨"),
                Thumbnail("https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/demonic_ach.png"),
            ),
            TextDisplay(f"-# Congrats to {author_string.name}!!"),
            accent_color=Colors.demonic,
        )
        container2 = Container(
            Section(
                TextDisplay(f"## 🌟 Demonic achievement unlocked!\n### Catnip Addict\nUncover the mafia's truth\nThanks for playing! ✨"),
                Thumbnail("https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/demonic_ach.png"),
            ),
            TextDisplay(f"-# Congrats to {author_string.name}!!"),
            accent_color=Colors.yellow,
        )
        view = LayoutView()
        view.add_item(container)
        view2 = LayoutView()
        view2.add_item(container2)

    try:
        result = None
        if send_type == "reply":
            result = await message.reply(view=view, flags=ach_flags)
        elif send_type == "send":
            result = await message.channel.send(view=view, flags=ach_flags)
        elif send_type == "followup":
            result = await message.followup.send(view=view, flags=ach_flags)
        elif send_type == "ephemeral":
            result = await message.followup.send(view=view, flags=ach_flags, ephemeral=True)
        elif send_type == "response":
            result = await message.response.send_message(view=view, flags=ach_flags)
        await progress(message, profile, "achievement")
        await finale(message, profile)
    except Exception:
        pass

    if result and ach_id == "thanksforplaying":
        await asyncio.sleep(2)
        await result.edit(view=view2)
        await asyncio.sleep(2)
        await result.edit(view=view)
        await asyncio.sleep(2)
        await result.edit(view=view2)
        await asyncio.sleep(2)
        await result.edit(view=view)
    elif result and ach_id == "curious":
        await result.delete(delay=30)


async def generate_quest(user: Profile, quest_type: str):
    while True:
        quest = random.choice(list(battle["quests"][quest_type].keys()))
        if quest == "prism":
            total_count = await Prism.count("guild_id = $1", user.guild_id)
            user_count = await Prism.count("guild_id = $1 AND user_id = $2", user.guild_id, user.user_id)
            global_boost = 0.06 * math.log(2 * total_count + 1)
            prism_boost = global_boost + 0.03 * math.log(2 * user_count + 1)
            if prism_boost < 0.15:
                continue
        elif quest == "news":
            global_user = await User.get_or_create(user_id=user.user_id)
            if len(news_list) <= len(global_user.news_state.strip()) and "0" not in global_user.news_state.strip()[-4:]:
                continue
        elif quest == "achievement":
            unlocked = 0
            for k in ach_names:
                if user[k] and ach_list[k]["category"] != "Hidden":
                    unlocked += 1
            if unlocked > 30:
                continue
        break

    quest_data = battle["quests"][quest_type][quest]
    if quest_type == "vote":
        user.vote_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.vote_cooldown = 0
    elif quest_type == "catch":
        user.catch_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.catch_quest = quest
        user.catch_cooldown = 0
    elif quest_type == "misc":
        user.misc_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.misc_quest = quest
        user.misc_cooldown = 0
    elif quest_type == "extra1":
        user.extra1_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.extra1_quest = quest
        user.extra1_cooldown = 0
    elif quest_type == "extra2":
        user.extra2_reward = random.randint(quest_data["xp_min"] // 10, quest_data["xp_max"] // 10) * 10
        user.extra2_quest = quest
        user.extra2_cooldown = 0
    await user.save()


async def refresh_quests(user):
    await user.refresh_from_db()
    start_date = datetime.datetime(2024, 12, 1)
    current_date = discord.utils.utcnow() + datetime.timedelta(hours=4)
    full_months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
    if current_date.day < start_date.day:
        full_months_passed -= 1
    if user.season != full_months_passed:
        user.bp_history = user.bp_history + f"{user.season},{user.battlepass},{user.progress};"
        user.battlepass = 0
        user.progress = 0

        user.catch_quest = ""
        user.catch_progress = 0
        user.catch_cooldown = 1
        user.catch_reward = 0

        user.misc_quest = ""
        user.misc_progress = 0
        user.misc_cooldown = 1
        user.misc_reward = 0

        user.extra1_quest = ""
        user.extra1_progress = 0
        user.extra1_cooldown = 1
        user.extra1_reward = 0

        user.extra2_quest = ""
        user.extra2_progress = 0
        user.extra2_cooldown = 1
        user.extra2_reward = 0

        user.season = full_months_passed
        await user.save()
    if 12 * 3600 < user.vote_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "vote")
    if 12 * 3600 < user.catch_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "catch")
    if 12 * 3600 < user.misc_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "misc")
    if 12 * 3600 < user.extra1_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "extra1")
    if 12 * 3600 < user.extra2_cooldown + 12 * 3600 < time.time():
        await generate_quest(user, "extra2")


async def progress(message: discord.Message | discord.Interaction, user: Profile, quest: str, is_belated: Optional[bool] = False):
    await refresh_quests(user)
    await user.refresh_from_db()

    # progress
    quest_complete = False
    current_xp = 0
    quest_data = None
    
    if user.catch_quest == quest:
        if user.catch_cooldown != 0:
            return
        quest_data = battle["quests"]["catch"][quest]
        user.catch_progress += 1
        if user.catch_progress >= quest_data["progress"]:
            quest_complete = True
            user.catch_cooldown = int(time.time())
            current_xp = user.progress + user.catch_reward
            user.catch_progress = 0
            user.reminder_catch = 1
    elif quest == "vote":
        if user.vote_cooldown != 0:
            return
        quest_data = battle["quests"]["vote"][quest]
        global_user = await User.get_or_create(user_id=user.user_id)
        user.vote_cooldown = global_user.vote_time_topgg

        # Weekdays 0 Mon - 6 Sun
        # double vote xp rewards if Friday, Saturday or Sunday
        voted_at = datetime.datetime.utcfromtimestamp(global_user.vote_time_topgg)
        if voted_at.weekday() >= 4:
            user.vote_reward *= 2

        streak_data = get_streak_reward(global_user.vote_streak)
        if streak_data["reward"]:
            user[f"pack_{streak_data['reward']}"] += 1
        current_xp = user.progress + user.vote_reward
        quest_complete = True
    elif user.misc_quest == quest:
        if user.misc_cooldown != 0:
            return
        quest_data = battle["quests"]["misc"][quest]
        user.misc_progress += 1
        if user.misc_progress >= quest_data["progress"]:
            quest_complete = True
            user.misc_cooldown = int(time.time())
            current_xp = user.progress + user.misc_reward
            user.misc_progress = 0
            user.reminder_misc = 1
    elif EXTRA_QUEST_TRIGGERS.get(user.extra1_quest) == quest:
        if user.extra1_cooldown != 0:
            return
        quest_data = battle["quests"]["extra1"][user.extra1_quest]
        user.extra1_progress += 1
        if user.extra1_progress >= quest_data["progress"]:
            quest_complete = True
            user.extra1_cooldown = int(time.time())
            current_xp = user.progress + user.extra1_reward
            user.extra1_progress = 0
        else:
            # Save progress even if quest not complete
            await user.save()
            return
    elif EXTRA_QUEST_TRIGGERS.get(user.extra2_quest) == quest:
        if user.extra2_cooldown != 0:
            return
        quest_data = battle["quests"]["extra2"][user.extra2_quest]
        user.extra2_progress += 1
        if user.extra2_progress >= quest_data["progress"]:
            quest_complete = True
            user.extra2_cooldown = int(time.time())
            current_xp = user.progress + user.extra2_reward
            user.extra2_progress = 0
        else:
            # Save progress even if quest not complete
            await user.save()
            return
    else:
        return

    await user.save()
    if not quest_complete:
        return

    user.quests_completed += 1

    # Apply all active XP bonuses (Noxx, vote streak, quests, prisms, etc.)
    _guild = message.guild if isinstance(message, discord.Message) else getattr(message, "guild", None)
    _prisms = await Prism.count("guild_id = $1 AND user_id = $2", user.guild_id, user.user_id) if _guild else 0
    _global_user = await User.get_or_create(user_id=user.user_id)
    _bonuses = await get_xp_bonuses(user, _global_user, _guild, _prisms)
    _multiplier = compute_xp_multiplier(_bonuses)
    if _multiplier > 1.0:
        current_xp = user.progress + round((current_xp - user.progress) * _multiplier)

    logging.debug("Quest complete: %s", quest)
    old_xp = user.progress
    level_complete_embeds = []
    if user.battlepass >= len(battle["seasons"][str(user.season)]):
        level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
        level_text = "Extra Rewards"
    else:
        level_data = battle["seasons"][str(user.season)][user.battlepass]
        level_text = f"Level {user.battlepass + 1}"

    if current_xp >= level_data["xp"]:
        logging.debug("Level complete %d", user.battlepass)
        xp_progress = current_xp
        active_level_data = level_data
        while xp_progress >= active_level_data["xp"]:
            user.battlepass += 1
            xp_progress -= active_level_data["xp"]
            user.progress = xp_progress
            cat_emojis = None
            if active_level_data["reward"] in cattypes:
                user[f"cat_{active_level_data['reward']}"] += active_level_data["amount"]
            elif active_level_data["reward"] == "Rain":
                user.rain_minutes += active_level_data["amount"]
                # --- Rain grant log (battlepass) ---
                try:
                    bp_rain_embed = discord.Embed(
                        title="☔ Rain Minutes Granted",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow(),
                    )
                    bp_rain_embed.add_field(name="User", value=str(user.user_id), inline=True)
                    bp_rain_embed.add_field(name="Source", value="Battlepass", inline=True)
                    bp_rain_embed.add_field(name="Minutes Added", value=str(active_level_data["amount"]), inline=True)
                    bp_rain_embed.add_field(name="Total Rain Minutes", value=str(user.rain_minutes), inline=True)
                    await log_rain(bp_rain_embed)
                except Exception as log_err:
                    logging.warning(f"Battlepass rain log failed: {log_err}")
            else:
                user[f"pack_{active_level_data['reward'].lower()}"] += 1
            await user.save()

            if not cat_emojis:
                if active_level_data["reward"] == "Rain":
                    description = f"You got ☔ {active_level_data['amount']} rain minutes!"
                elif active_level_data["reward"] in cattypes:
                    description = (
                        f"You got {get_emoji(active_level_data['reward'].lower() + 'cat')} {active_level_data['amount']} {active_level_data['reward']}!"
                    )
                else:
                    description = (
                        f"You got a {get_emoji(active_level_data['reward'].lower() + 'pack')} {active_level_data['reward']} pack! Do /packs to open it!"
                    )
                title = f"Level {user.battlepass} Complete!"
            else:
                description = f"You got {cat_emojis}!"
                title = "Bonus Complete!"
            embed_level_up = discord.Embed(title=title, description=description, color=Colors.yellow)
            level_complete_embeds.append(embed_level_up)

            if user.battlepass >= len(battle["seasons"][str(user.season)]):
                active_level_data = {"xp": 1500, "reward": "Stone", "amount": 1}
                new_level_text = "Extra Rewards"
            else:
                active_level_data = battle["seasons"][str(user.season)][user.battlepass]
                new_level_text = f"Level {user.battlepass + 1}"

        embed_progress = await progress_embed(
            message,
            user,
            active_level_data,
            xp_progress,
            0,
            quest_data,
            current_xp - old_xp,
            new_level_text,
        )

    else:
        user.progress = current_xp
        await user.save()
        embed_progress = await progress_embed(
            message,
            user,
            level_data,
            current_xp,
            old_xp,
            quest_data,
            current_xp - old_xp,
            level_text,
        )

    if is_belated:
        embed_progress.set_footer(text="For catching within 3 seconds")

    if _multiplier > 1.0:
        active_labels = ", ".join(b["label"] for b in _bonuses if b["active"])
        existing_footer = embed_progress.footer.text or ""
        footer = (f"⚡ {_multiplier:.2f}x XP — {active_labels} | " + existing_footer).rstrip(" |")
        embed_progress.set_footer(text=footer)

    if level_complete_embeds:
        await message.channel.send(f"<@{user.user_id}>", embeds=level_complete_embeds + [embed_progress])
    else:
        await message.channel.send(f"<@{user.user_id}>", embed=embed_progress)


async def progress_embed(message, user, level_data, current_xp, old_xp, quest_data, diff, level_text) -> discord.Embed:
    percentage_before = int(old_xp / level_data["xp"] * 10)
    percentage_after = int(current_xp / level_data["xp"] * 10)
    percenteage_left = 10 - percentage_after

    progress_line = get_emoji("staring_square") * percentage_before + "🟨" * (percentage_after - percentage_before) + "⬛" * percenteage_left

    title = quest_data["title"] if "top.gg" not in quest_data["title"] else "Vote on Top.gg"

    if level_data["reward"] == "Rain":
        reward_text = get_emoji(str(level_data["amount"]) + "rain")
    elif level_data["reward"] == "random cats":
        reward_text = f"{level_data['amount']}x ❓"
    elif level_data["reward"] in cattypes:
        reward_text = f"{level_data['amount']}x {get_emoji(level_data['reward'].lower() + 'cat')}"
    else:
        reward_text = get_emoji(level_data["reward"].lower() + "pack")

    global_user = await User.get_or_create(user_id=user.user_id)
    streak_data = get_streak_reward(global_user.vote_streak)
    if streak_data["reward"] and "top.gg" in quest_data["title"]:
        streak_reward = f"\n🔥 **Streak Bonus!** +1 {streak_data['emoji']} {streak_data['reward'].capitalize()} pack"
    else:
        streak_reward = ""

    return discord.Embed(
        title=f"✅ {title}",
        description=f"{progress_line} {reward_text}\n{current_xp}/{level_data['xp']} XP (+{diff}){streak_reward}",
        color=Colors.green,
    ).set_author(name="/battlepass " + level_text)


async def debt_cutscene(message, user):
    if user.debt_seen:
        return

    user.debt_seen = True
    await user.save()

    debt_msgs = [
        "**\\*BANG\\***",
        "Your door gets slammed open and multiple man in black suits enter your room.",
        "**???**: Hello, you have unpaid debts. You owe us money. We are here to liquidate all your assets.",
        "*(oh for fu)*",
        "**You**: pls dont",
        "**???**: oh okay then we will come back to you later.",
        "They leave the room.",
        "**You**: Oh god this is bad",
        "**You**: I know of a solution though!",
        "**You**: I heard you can gamble your debts away in the slots machine!",
    ]

    for debt_msg in debt_msgs:
        await asyncio.sleep(4)
        await message.followup.send(debt_msg, ephemeral=True)


async def finale(message, user):
    if user.finale_seen:
        return

    # check ach req
    for k in ach_names:
        if not user[k] and ach_list[k]["category"] != "Hidden":
            return

    user.finale_seen = True
    await user.save()
    try:
        author_string = message.author
    except Exception:
        author_string = message.user
    await asyncio.sleep(5)
    await message.channel.send("...")
    await asyncio.sleep(3)
    await message.channel.send("You...")
    await asyncio.sleep(3)
    await message.channel.send("...actually did it.")
    await asyncio.sleep(3)
    await message.channel.send(
        embed=discord.Embed(
            title="True Ending achieved!",
            description="You are finally free.",
            color=Colors.rose,
        )
        .set_author(
            name="All achievements complete!",
            icon_url="https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png",
        )
        .set_footer(text=f"Congrats to {author_string}")
    )
