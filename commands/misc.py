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
import asyncio, base64, datetime, io, logging, random, re, time
import aiohttp, discord
from discord import ButtonStyle
from discord.ui import Button, LayoutView, Modal, TextInput, TextDisplay, Container, Section, Thumbnail, ActionRow, MediaGallery

import shared
import shared
from constants import (cattypes, type_dict, cattype_lc_dict, cat_facts_list, NONOWORDS, VIEW_TIMEOUT, news_list,
    CAT_TRIVIA, rain_shill)
from core.colors import Colors
from core.utils import get_emoji, do_funny, fetch_dm_channel
from database import Channel, Profile, User, Reminder
from achievements import achemb, progress
from gui.components import Container as CustomContainer


@shared.bot.tree.command(description="vote for cattito")
async def vote(message: discord.Interaction):
    view = LayoutView(timeout=1)
    button = Button(label="Vote!", url="https://top.gg/bot/1387860417706987590/vote", emoji=get_emoji("topgg"))
    view.add_item(button)
    await message.response.send_message(view=view)


@shared.bot.tree.command(description="Get Daily cats")
async def daily(message: discord.Interaction):
    await message.response.send_message("there is no daily cats why did you even try this")
    await achemb(message, "daily", "followup")


@shared.bot.tree.command(description="Read text as TikTok TTS woman")
@discord.app_commands.describe(text="The text to be read! (300 characters max)")
async def tiktok(message: discord.Interaction, text: str):
    # detect n-words
    for i in NONOWORDS:
        if i in text.lower():
            await message.response.send_message("Do not.", ephemeral=True)
            return

    await message.response.defer()
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    if text == "bwomp":
        file = discord.File("bwomp.mp3", filename="bwomp.mp3")
        await message.followup.send(file=file)
        await achemb(message, "bwomp", "followup")
        await progress(message, profile, "tiktok")
        return

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://tiktok-tts.weilnet.workers.dev/api/generation",
                json={"text": text, "voice": "en_us_001"},
                headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
            ) as response:
                stuff = await response.json()
                with io.BytesIO() as f:
                    ba = "data:audio/mpeg;base64," + stuff["data"]
                    f.write(base64.b64decode(ba))
                    f.seek(0)
                    await message.followup.send(file=discord.File(fp=f, filename="output.mp3"))
        except discord.NotFound:
            pass
        except Exception:
            await message.followup.send("i dont speak guacamole (remove non-english characters, make sure the message is below 300 characters)")

    await progress(message, profile, "tiktok")


@shared.bot.tree.command(description="the most useful command ever")
async def bruh(message: discord.Interaction):
    await message.response.defer()
    await message.delete_original_response()


@shared.bot.tree.command(description="get a reminder in the future (+- 5 minutes)")
@discord.app_commands.describe(
    days="in how many days",
    hours="in how many hours",
    minutes="in how many minutes (+- 5 minutes)",
    text="what to remind",
)
async def remind(
    message: discord.Interaction,
    days: Optional[int],
    hours: Optional[int],
    minutes: Optional[int],
    text: Optional[str],
):
    if not days:
        days = 0
    if not hours:
        hours = 0
    if not minutes:
        minutes = 0
    if not text:
        text = "Reminder!"

    goal_time = int(time.time() + (days * 86400) + (hours * 3600) + (minutes * 60))
    if goal_time > time.time() + (86400 * 365 * 20):
        await message.response.send_message("cats do not live for that long", ephemeral=True)
        return
    if len(text) > 1900:
        await message.response.send_message("thats too long", ephemeral=True)
        return
    if goal_time < 0:
        await message.response.send_message("cat cant time travel (yet)", ephemeral=True)
        return
    await message.response.send_message(f"🔔 ok, <t:{goal_time}:R> (+- 5 min) ill remind you of:\n{text}")
    msg = await message.original_response()
    message_link = msg.jump_url
    text += f"\n\n*This is a [reminder](<{message_link}>) you set.*"
    await Reminder.create(user_id=message.user.id, text=text, time=goal_time)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    profile.reminders_set += 1
    await profile.save()
    await achemb(message, "reminder", "followup")  # the ai autocomplete thing suggested this and its actually a cool ach
    await progress(message, profile, "reminder")  # the ai autocomplete thing also suggested this though profile wasnt defined


@shared.bot.tree.command(name="random", description="Get a random cat")
async def random_cat(message: discord.Interaction):
    await message.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://api.thecatapi.com/v1/images/search", headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"}
            ) as response:
                data = await response.json()
                await message.followup.send(data[0]["url"])
                await achemb(message, "randomizer", "followup")
                user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
                await progress(message, user, "random")
        except Exception:
            await message.followup.send("no cats :(")


@shared.bot.tree.command(description="define a word")
async def define(message: discord.Interaction, word: str):
    word = word.lower()

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}",
                headers={"User-Agent": "CatBot/1.0 https://github.com/milenakos/cat-bot"},
            ) as response:

                if response.status != 200:
                    raise Exception

                data = await response.json()

                definition = None
                source = "https://dictionaryapi.dev/"

                for entry in data:
                    for meaning in entry.get("meanings", []):
                        for d in meaning.get("definitions", []):
                            if "definition" in d:
                                definition = d["definition"]
                                break
                        if definition:
                            break
                    if definition:
                        break

                if not definition:
                    raise Exception

                text = definition.lower()

                await message.response.send_message(
                    f"__{word}__\n{definition}\n-# Powered by [Free Dictionary API](<{source}>)",
                    ephemeral=any(test in text for test in [
                        "vulgar", "slur", "offensive", "profane", "insult", "abusive", "derogatory"
                    ]),
                )

                await achemb(message, "define", "followup")
                user = await Profile.get_or_create(
                    guild_id=message.guild.id,
                    user_id=message.user.id
                )
                await progress(message, user, "define")

        except Exception:
            await message.response.send_message(
                "no definition found",
                ephemeral=True
            )


@shared.bot.tree.command(name="fact", description="get a random cat fact")
async def cat_fact(message: discord.Interaction):
    facts = [
        "you love cats",
        f"cattito is in {len(shared.bot.guilds):,} servers",
        "cat",
        "cats are the best",
    ]

    # give a fact from the list or the file
    if random.randint(0, 10) == 0:
        await message.response.send_message(random.choice(facts))
    else:
        await message.response.send_message(random.choice(cat_facts_list))

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    user.facts += 1
    await user.save()
    if user.facts >= 10:
        await achemb(message, "fact_enjoyer", "followup")
    await progress(message, user, "fact")

    try:
        channel = await Channel.get_or_none(channel_id=message.channel.id)
        if channel and channel.cattype == "Professor":
            await achemb(message, "nerd_battle", "followup")
    except Exception:
        pass



# ── /coinflip ──────────────────────────────────────────────────────────────
@shared.bot.tree.command(name="coinflip", description="Flip a coin and bet cats on it!")
@discord.app_commands.describe(
    choice="heads or tails",
    bet="how many Fine cats to bet (1-50, optional)"
)
async def coinflip(message: discord.Interaction, choice: str, bet: Optional[int]):
    if message.guild is None:
        await message.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    choice = choice.lower().strip()
    if choice not in ("heads", "tails", "h", "t"):
        await message.response.send_message(
            "Pick **heads** or **tails**!", ephemeral=True
        )
        return
    if choice in ("h",):
        choice = "heads"
    elif choice in ("t",):
        choice = "tails"

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    # Handle bet
    winnings = 0
    bet_text = ""
    if bet is not None:
        if bet < 1 or bet > 50:
            await message.response.send_message("Bet must be between 1 and 50 Fine cats.", ephemeral=True)
            return
        if user.cat_Fine < bet:
            await message.response.send_message(
                f"You only have {user.cat_Fine} Fine cats!", ephemeral=True
            )
            return
        winnings = bet

    result = random.choice(["heads", "tails"])
    won = result == choice
    coin_emoji = "🪙"

    if won:
        result_text = f"**{result.upper()}!** You win!"
        color = Colors.green
        if winnings:
            user.cat_Fine += winnings
            bet_text = f"\n+{winnings} {get_emoji('finecat')} Fine cats!"
    else:
        result_text = f"**{result.upper()}!** You lose!"
        color = Colors.red
        if winnings:
            user.cat_Fine -= winnings
            bet_text = f"\n-{winnings} {get_emoji('finecat')} Fine cats!"

    await user.save()

    embed = discord.Embed(
        title=f"{coin_emoji} Coin Flip",
        description=f"You chose **{choice}** — {result_text}{bet_text}",
        color=color,
    )
    await message.response.send_message(embed=embed)

    await progress(message, user, "coinflip")
    await progress(message, user, "any_game")
    if won:
        await progress(message, user, "coinflip_win")


# ── /catquiz ──────────────────────────────────────────────────────────────
CAT_TRIVIA = CAT_TRIVIA

@shared.bot.tree.command(name="catquiz", description="Test your cat knowledge for bonus XP!")
async def catquiz(message: discord.Interaction):
    if message.guild is None:
        await message.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    await message.response.defer()
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)

    q = random.choice(CAT_TRIVIA)
    choices = q["choices"][:]
    random.shuffle(choices)

    # Build answer buttons
    answered = False

    async def make_view(disabled=False, selected=None):
        view = LayoutView(timeout=30)
        for opt in choices:
            is_correct = (opt == q["a"])
            if disabled:
                if opt == q["a"]:
                    style = ButtonStyle.green
                elif opt == selected and not is_correct:
                    style = ButtonStyle.red
                else:
                    style = ButtonStyle.grey
            else:
                style = ButtonStyle.blurple
            btn = Button(label=opt, style=style, disabled=disabled)
            if not disabled:
                async def make_cb(answer=opt):
                    async def cb(interaction: discord.Interaction):
                        nonlocal answered
                        if interaction.user.id != message.user.id:
                            await interaction.response.send_message("This isn't your quiz!", ephemeral=True)
                            return
                        if answered:
                            return
                        answered = True
                        correct = (answer == q["a"])
                        result_view = await make_view(disabled=True, selected=answer)
                        if correct:
                            result_embed = discord.Embed(
                                title="✅ Correct!",
                                description=f"**{q['q']}**\n\nAnswer: **{q['a']}**\n\n-# {q['fun']}",
                                color=Colors.green,
                            )
                        else:
                            result_embed = discord.Embed(
                                title="❌ Wrong!",
                                description=f"**{q['q']}**\n\nCorrect answer: **{q['a']}**\n\n-# {q['fun']}",
                                color=Colors.red,
                            )
                        await interaction.response.edit_message(embed=result_embed, view=result_view)
                        await progress(message, user, "quiz_complete")
                        if correct:
                            await progress(message, user, "quiz_correct")
                    return cb
                btn.callback = await make_cb(opt)
            view.add_item(btn)
        return view

    embed = discord.Embed(
        title="🐱 Cat Trivia!",
        description=f"**{q['q']}**\n\nPick your answer below:",
        color=Colors.brown,
    )
    view = await make_view()
    await message.followup.send(embed=embed, view=view)


@shared.bot.tree.command(name="howcat", description="Find out how much of a cat you are today")
@discord.app_commands.describe(user="Who to test (defaults to you)")
async def howcat(message: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or message.user
    # Seed by user id + date so it's consistent for the day but changes daily
    seed = target.id + int(datetime.date.today().toordinal())
    rng = random.Random(seed)
    percent = rng.randint(0, 100)

    if percent == 100:
        verdict = "you ARE a cat. please see a doctor"
    elif percent >= 85:
        verdict = "basically a cat at this point"
    elif percent >= 65:
        verdict = "more cat than human honestly"
    elif percent >= 45:
        verdict = "cat-human hybrid. scientists are baffled"
    elif percent >= 25:
        verdict = "mostly human but suspicious behaviour detected"
    elif percent >= 10:
        verdict = "barely any cat detected. disappointing"
    else:
        verdict = "cat scientists are concerned. please seek catification"

    bar_filled = round(percent / 10)
    bar = "🟧" * bar_filled + "⬛" * (10 - bar_filled)

    embed = discord.Embed(
        title=f"🐱 How cat is {target.display_name}?",
        description=f"{bar} **{percent}%**\n\n*{verdict}*",
        color=Colors.brown,
    )
    embed.set_footer(text="Results reset daily")
    await message.response.send_message(embed=embed)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, profile, "any_game")


@shared.bot.tree.command(name="compare", description="Compare your cat collection with another user")
@discord.app_commands.describe(user="Who to compare with")
async def compare(message: discord.Interaction, user: discord.Member):
    if user.id == message.user.id:
        await message.response.send_message("comparing yourself to yourself... big ego or big loneliness?", ephemeral=True)
        return

    await message.response.defer()

    me = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    them = await Profile.get_or_create(guild_id=message.guild.id, user_id=user.id)

    def total_cats(p):
        return sum(getattr(p, f"cat_{t}", 0) or 0 for t in cattypes)

    def rarity_score(p):
        return sum((getattr(p, f"cat_{t}", 0) or 0) * (1001 - v) for t, v in type_dict.items())

    me_total = total_cats(me)
    them_total = total_cats(them)
    me_score = rarity_score(me)
    them_score = rarity_score(them)

    def winner_str(a, b, reverse=False):
        if a == b:
            return "🟡 tie"
        if (a > b) != reverse:
            return f"✅ {message.user.display_name}"
        return f"✅ {user.display_name}"

    embed = discord.Embed(
        title=f"⚖️ {message.user.display_name} vs {user.display_name}",
        color=Colors.brown,
    )
    embed.add_field(
        name="Total Cats",
        value=f"{message.user.display_name}: **{me_total:,}**\n{user.display_name}: **{them_total:,}**\n{winner_str(me_total, them_total)}",
        inline=True,
    )
    embed.add_field(
        name="Rarity Score",
        value=f"{message.user.display_name}: **{me_score:,}**\n{user.display_name}: **{them_score:,}**\n{winner_str(me_score, them_score)}",
        inline=True,
    )

    # Rarest cat each person has
    def rarest(p):
        for cat_type in reversed(cattypes):  # rarest last in list
            if (getattr(p, f"cat_{cat_type}", 0) or 0) > 0:
                return cat_type
        return None

    me_rarest = rarest(me)
    them_rarest = rarest(them)
    me_rarest_str = f"{get_emoji(me_rarest.lower() + 'cat')} {me_rarest}" if me_rarest else "none :("
    them_rarest_str = f"{get_emoji(them_rarest.lower() + 'cat')} {them_rarest}" if them_rarest else "none :("

    embed.add_field(
        name="Rarest Cat",
        value=f"{message.user.display_name}: {me_rarest_str}\n{user.display_name}: {them_rarest_str}",
        inline=False,
    )

    await message.followup.send(embed=embed)
    await progress(message, me, "any_game")


@shared.bot.tree.command(name="catstatus", description="Check what your cat is doing right now")
async def catstatus(message: discord.Interaction):
    activities = [
        "knocking things off shelves",
        "judging you",
        "sleeping in an inconvenient location",
        "staring at a wall",
        "running at 3am for no reason",
        "sitting in a box",
        "demanding food and then walking away",
        "licking themselves aggressively",
        "ignoring you",
        "plotting something",
        "vibing",
        "yeeting a plant",
        "being cute to avoid consequences",
        "malfunctioning",
        "collecting rare butterflies",
        "thinking about cheese",
        "touching grass (one blade)",
        "doing taxes",
        "becoming one with the void",
        "speedrunning napping",
    ]
    locations = [
        "on your keyboard",
        "under the bed",
        "on top of the fridge",
        "inside a bag you left on the floor",
        "on the forbidden chair",
        "behind the TV",
        "in the sink",
        "on your clean laundry",
        "in the quantum realm",
        "somewhere you haven't checked yet",
        "on the windowsill judging the mailman",
        "in the pocket dimension",
    ]

    rng = random.Random(message.user.id + int(time.time() // 3600))
    activity = rng.choice(activities)
    location = rng.choice(locations)
    mood = rng.randint(0, 100)

    mood_emoji = "😺" if mood > 70 else "😾" if mood < 30 else "😼"

    embed = discord.Embed(
        title=f"🐾 {message.user.display_name}'s Cat Status",
        description=f"**Currently:** {activity}\n**Location:** {location}\n**Mood:** {mood_emoji} {mood}/100",
        color=Colors.brown,
    )
    embed.set_footer(text="Status updates every hour")
    await message.response.send_message(embed=embed)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, profile, "any_game")


@shared.bot.tree.command(name="send", description="Send one of your cats to another user!")
@discord.app_commands.describe(
    user="Who to send a cat to",
    cat_type="Which type of cat to gift (e.g. Nice, Rare, Divine...)",
    amount="How many to gift (default 1)",
)
async def gift(message: discord.Interaction, user: discord.Member, cat_type: str, amount: Optional[int] = 1):
    if user.id == message.user.id:
        await message.response.send_message("you can't gift cats to yourself... be generous 🐱", ephemeral=True)
        return
    if user.bot:
        await message.response.send_message("bots don't need cats (or do they?)", ephemeral=True)
        return
    if amount is None or amount < 1:
        await message.response.send_message("gotta gift at least 1 cat!", ephemeral=True)
        return
    if amount > 100:
        await message.response.send_message("woah that's generous but 100 max please", ephemeral=True)
        return

    # Normalise cat type
    cat_key = cattype_lc_dict.get(cat_type.lower())
    if not cat_key:
        options = ", ".join(cattypes[:10]) + "..."
        await message.response.send_message(
            f"unknown cat type `{cat_type}`. try something like: {options}", ephemeral=True
        )
        return

    await message.response.defer()

    giver = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    receiver = await Profile.get_or_create(guild_id=message.guild.id, user_id=user.id)

    attr = f"cat_{cat_key}"
    giver_count = getattr(giver, attr, 0) or 0

    if giver_count < amount:
        await message.followup.send(
            f"you only have **{giver_count}** {get_emoji(cat_key.lower() + 'cat')} {cat_key} cat(s), can't gift {amount}!",
            ephemeral=True,
        )
        return

    # Transfer
    setattr(giver, attr, giver_count - amount)
    receiver_count = getattr(receiver, attr, 0) or 0
    setattr(receiver, attr, receiver_count + amount)
    await giver.save()
    await receiver.save()

    cat_emoji = get_emoji(cat_key.lower() + "cat")
    embed = discord.Embed(
        title="🎁 Cat Gift!",
        description=f"{message.user.mention} gifted **{amount}x {cat_emoji} {cat_key}** cat(s) to {user.mention}!\n\nhow sweet 🐾",
        color=Colors.green,
    )
    await message.followup.send(embed=embed)
    await achemb(message, "generous", "followup")
    await progress(message, giver, "gift")


@shared.bot.tree.command(name="streak", description="Check your catching streak and daily activity")
@discord.app_commands.describe(user="Whose streak to check (defaults to you)")
async def streak(message: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or message.user
    await message.response.defer()

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=target.id)
    global_user = await User.get_or_create(user_id=target.id)

    total = sum(getattr(profile, f"cat_{t}", 0) or 0 for t in cattypes)
    vote_streak = getattr(global_user, "vote_streak", 0) or 0

    # Pick a streak flavour text
    if vote_streak == 0:
        streak_text = "no vote streak yet — vote for cattito to start one!"
    elif vote_streak < 3:
        streak_text = "just getting started 🐾"
    elif vote_streak < 7:
        streak_text = "building momentum! 🔥"
    elif vote_streak < 14:
        streak_text = "on a roll! 🔥🔥"
    elif vote_streak < 30:
        streak_text = "dedicated cat fan! 🔥🔥🔥"
    else:
        streak_text = "LEGENDARY STREAK! you live and breathe cats 🐱👑"

    embed = discord.Embed(
        title=f"📊 {target.display_name}'s Cat Stats",
        color=Colors.brown,
    )
    embed.add_field(name="🐾 Cats in This Server", value=f"{total:,}", inline=True)
    embed.add_field(name="🗳️ Vote Streak", value=f"{vote_streak} day(s)", inline=True)
    embed.add_field(name="💬 Streak Verdict", value=streak_text, inline=False)

    await message.followup.send(embed=embed)
    me = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, me, "any_game")


# ── /catfight ──────────────────────────────────────────────────────────────
@shared.bot.tree.command(name="catfight", description="Challenge another user to a cat duel!")
@discord.app_commands.describe(opponent="Who do you want to fight?")
async def catfight(message: discord.Interaction, opponent: discord.Member):
    if opponent.id == message.user.id:
        await message.response.send_message("you can't fight yourself... or can you? (no)", ephemeral=True)
        return
    if opponent.bot:
        await message.response.send_message("bots don't fight fair 😤", ephemeral=True)
        return

    challenger = message.user

    # ── Moves available each turn ─────────────────────────────────────────────
    MOVES = {
        "🐾 Scratch":   {"damage": (8, 15),  "crit_chance": 0.10, "label": "🐾 Scratch",   "desc": "scratches with sharp claws"},
        "💨 Pounce":    {"damage": (12, 22), "crit_chance": 0.15, "label": "💨 Pounce",    "desc": "leaps with full force"},
        "😾 Hiss":      {"damage": (5, 10),  "crit_chance": 0.05, "label": "😾 Hiss",      "desc": "emits a terrifying hiss", "stun_chance": 0.25},
        "🍑 Sit On":    {"damage": (6, 12),  "crit_chance": 0.05, "label": "🍑 Sit On",    "desc": "deploys maximum weight"},
        "🌀 Hairball":  {"damage": (15, 25), "crit_chance": 0.20, "label": "🌀 Hairball",  "desc": "launches a disgusting projectile"},
        "😺 Meow":      {"damage": (3, 8),   "crit_chance": 0.0,  "label": "😺 Meow",      "desc": "meows so loudly it hurts", "heal": (5, 10)},
    }

    # ── HP calculation from cat collection ────────────────────────────────────
    def base_hp(profile):
        total = sum(getattr(profile, f"cat_{t}", 0) or 0 for t in cattypes)
        return max(60, min(150, 60 + total // 5))

    profile_c = await Profile.get_or_create(guild_id=message.guild.id, user_id=challenger.id)
    profile_o = await Profile.get_or_create(guild_id=message.guild.id, user_id=opponent.id)

    state = {
        "hp": {challenger.id: base_hp(profile_c), opponent.id: base_hp(profile_o)},
        "max_hp": {challenger.id: base_hp(profile_c), opponent.id: base_hp(profile_o)},
        "stunned": {challenger.id: False, opponent.id: False},
        "turn": challenger.id,      # challenger moves first after opponent accepts
        "log": [],
        "active": False,            # becomes True once opponent accepts
        "over": False,
    }

    def hp_bar(current, maximum):
        filled = round((current / maximum) * 10)
        filled = max(0, min(10, filled))
        pct = current / maximum
        bar_char = "🟩" if pct > 0.5 else ("🟨" if pct > 0.25 else "🟥")
        return bar_char * filled + "⬛" * (10 - filled)

    def make_status_embed(title="⚔️ Cat Fight!", color=Colors.maroon):
        c_hp = state["hp"][challenger.id]
        o_hp = state["hp"][opponent.id]
        c_max = state["max_hp"][challenger.id]
        o_max = state["max_hp"][opponent.id]

        desc = (
            f"**{challenger.display_name}** {hp_bar(c_hp, c_max)} `{c_hp}/{c_max} HP`\n"
            f"**{opponent.display_name}** {hp_bar(o_hp, o_max)} `{o_hp}/{o_max} HP`\n"
        )
        if state["log"]:
            desc += "\n**Battle Log:**\n" + "\n".join(f"• {l}" for l in state["log"][-4:])

        current_fighter = challenger if state["turn"] == challenger.id else opponent
        if state["active"] and not state["over"]:
            desc += f"\n\n*{current_fighter.display_name}'s turn — pick a move!*"

        embed = discord.Embed(title=title, description=desc, color=color)
        return embed

    def make_move_view(whose_turn_id):
        view = LayoutView(timeout=60)
        for move_key, move_data in MOVES.items():
            btn = Button(label=move_data["label"], style=ButtonStyle.blurple)

            async def move_cb(interaction: discord.Interaction, mk=move_key, md=move_data):
                nonlocal state
                if interaction.user.id != state["turn"]:
                    await interaction.response.send_message("it's not your turn! 🐱", ephemeral=True)
                    return
                if state["over"]:
                    await interaction.response.defer()
                    return

                await interaction.response.defer()

                attacker = interaction.user
                defender = opponent if attacker.id == challenger.id else challenger

                log_line = f"**{attacker.display_name}** {md['desc']}"

                # Stun check — skip turn if stunned
                if state["stunned"][attacker.id]:
                    state["stunned"][attacker.id] = False
                    state["log"].append(f"**{attacker.display_name}** is stunned and skips their turn!")
                    state["turn"] = defender.id
                    await interaction.edit_original_response(embed=make_status_embed(), view=make_move_view(state["turn"]))
                    return

                # Healing move
                if "heal" in md:
                    heal_amt = random.randint(*md["heal"])
                    state["hp"][attacker.id] = min(state["max_hp"][attacker.id], state["hp"][attacker.id] + heal_amt)
                    log_line += f" (+{heal_amt} HP)"

                # Damage
                dmg = random.randint(*md["damage"])
                crit = random.random() < md["crit_chance"]
                if crit:
                    dmg = int(dmg * 1.75)
                    log_line += f" — **CRIT!** 💥 -{dmg} HP"
                else:
                    log_line += f" — -{dmg} HP"

                state["hp"][defender.id] = max(0, state["hp"][defender.id] - dmg)

                # Stun chance
                if "stun_chance" in md and random.random() < md["stun_chance"]:
                    state["stunned"][defender.id] = True
                    log_line += " *(stunned!)*"

                state["log"].append(log_line)

                # Check if battle is over
                if state["hp"][defender.id] <= 0:
                    state["over"] = True
                    win_embed = make_status_embed(
                        title=f"🏆 {attacker.display_name} wins!",
                        color=Colors.green,
                    )
                    win_embed.set_footer(text="gg no re 🐾")
                    await interaction.edit_original_response(embed=win_embed, view=None)
                    await achemb(message, "any_game", "followup")
                    await progress(message, profile_c, "any_game")
                    return

                # Swap turn
                state["turn"] = defender.id
                await interaction.edit_original_response(embed=make_status_embed(), view=make_move_view(state["turn"]))

            btn.callback = move_cb
            view.add_item(btn)
        return view

    # ── Challenge embed with Accept / Decline ─────────────────────────────────
    challenge_embed = discord.Embed(
        title="⚔️ Cat Fight Challenge!",
        description=(
            f"{opponent.mention}, **{challenger.display_name}** wants to fight you!\n\n"
            f"Your HP: `{state['hp'][opponent.id]}` · Their HP: `{state['hp'][challenger.id]}`\n\n"
            f"*You have 60 seconds to accept or decline.*"
        ),
        color=Colors.maroon,
    )

    accept_view = LayoutView(timeout=60)
    accept_btn = Button(label="✅ Accept", style=ButtonStyle.green)
    decline_btn = Button(label="❌ Decline", style=ButtonStyle.red)

    async def accept_cb(interaction: discord.Interaction):
        if interaction.user.id != opponent.id:
            await interaction.response.send_message("this challenge isn't for you 🐱", ephemeral=True)
            return
        state["active"] = True
        await interaction.response.edit_message(
            embed=make_status_embed(title="⚔️ Cat Fight! — Fight started!"),
            view=make_move_view(state["turn"]),
        )

    async def decline_cb(interaction: discord.Interaction):
        if interaction.user.id not in (opponent.id, challenger.id):
            await interaction.response.send_message("not your business 🐾", ephemeral=True)
            return
        declined_embed = discord.Embed(
            title="❌ Challenge Declined",
            description=f"**{opponent.display_name}** backed down from the fight. 🐈",
            color=Colors.red,
        )
        await interaction.response.edit_message(embed=declined_embed, view=None)

    async def challenge_timeout():
        try:
            if not state["active"]:
                timeout_embed = discord.Embed(
                    title="⏰ Challenge Expired",
                    description=f"{opponent.display_name} didn't respond in time.",
                    color=Colors.red,
                )
                await message.edit_original_response(embed=timeout_embed, view=None)
        except Exception:
            pass

    accept_view.on_timeout = challenge_timeout
    accept_btn.callback = accept_cb
    decline_btn.callback = decline_cb
    accept_view.add_item(accept_btn)
    accept_view.add_item(decline_btn)

    await message.response.send_message(embed=challenge_embed, view=accept_view)
