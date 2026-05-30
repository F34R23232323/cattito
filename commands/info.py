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
import asyncio, datetime, logging, math, platform, random, subprocess, sys, time
import aiohttp, discord, psutil
from discord import ButtonStyle
from discord.ui import Button, LayoutView, Container, Section, TextDisplay, Thumbnail, ActionRow, MediaGallery
# MediaGalleryItem is accessed via discord.MediaGalleryItem
import config
import shared
from shared import gen_credits, OWNER_IDS, loop_count, temp_cookie_storage
import shared
from constants import cattypes, type_dict, news_list, VIEW_TIMEOUT, rain_shill
from core.colors import Colors
from core.utils import get_emoji, do_funny, fetch_dm_channel, format_timedelta
from database import Channel, Profile, Prism, User
from achievements import achemb, progress
from gui.components import Container as CustomContainer
from systems.xp_bonus import get_xp_bonuses, compute_xp_multiplier


@shared.bot.tree.command(description="Learn to use the bot")
async def help(message):
    view = LayoutView(timeout=VIEW_TIMEOUT)

    setup_container = Container(
        Section(
            TextDisplay(
                "## 🐾 How to Setup\n"
                "A server moderator (anyone with *Manage Server* permission) needs to run `/setup` in any channel. "
                "After that, cats will start to spawn in 1–10 minute intervals inside that channel.\n\n"
                "You can customize those intervals with `/changetimings` and change the spawn message with `/changemessage`.\n"
                "Cat spawns can also be forced by moderators using `/forcespawn`.\n"
                "You can have unlimited setup channels at once, and stop spawning in a channel with `/forget`."
            ),
            Thumbnail("https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png"),
        ),
        accent_color=Colors.brown,
    )

    play_container = Container(
        "## 🎮 How to Play",
        "===",
        "**Catch Cats**\n"
        'Whenever a cat spawns you\'ll see a message like "a cat has appeared", displaying its type. '
        "Cat types have varying rarities from 25% for Fine to hundredths of a percent for the rarest types. "
        'Say "cat" to catch it and add it to your inventory.',
        "===",
        "**Viewing Your Inventory**\n"
        "Use `/inventory` to view your (or anyone else's!) collection along with other stats. "
        "Each server has a separate inventory to keep things fair and fun. "
        "Check the `/leaderboards`, and use `/gift` or `/trade` to transfer cats.",
        "===",
        "**Let's get funky!**\n"
        'cattito has tons of extra mechanics — collect `/achievements`, progress in the `/battlepass`, '
        "or get into catnip debt with the mafia. The limit is how much you worship!",
        "===",
        "**Other features**\n"
        "Many more commands to discover along the way. "
        "Anything unclear? Check out [our wiki](https://cattito.fun) or join our [Discord server](https://discord.gg/kyynVDzcJs).",
        "===",
        f"-# cattito by Milenakos, {discord.utils.utcnow().year}",
        accent_color=Colors.brown,
    )

    view.add_item(setup_container)
    view.add_item(play_container)
    await message.response.send_message(view=view)


@shared.bot.tree.command(description="Roll the credits")
async def credits(message: discord.Interaction):
    global gen_credits

    if not gen_credits:
        await message.response.send_message(
            "credits not yet ready! this is a very rare error, congrats.",
            ephemeral=True,
        )
        return

    await message.response.defer()

    credits_text = gen_credits.get("text", "")
    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(Container(
        Section(
            TextDisplay(f"## cattito\n{credits_text}"),
            Thumbnail("https://wsrv.nl/?url=raw.githubusercontent.com/milenakos/cat-bot/main/images/cat.png"),
        ),
        accent_color=Colors.brown,
    ))
    await message.followup.send(view=view)


@shared.bot.tree.command(description="View various bot information and stats")
async def info(message: discord.Interaction):
    try:
        git_timestamp = int(subprocess.check_output(["git", "show", "-s", "--format=%ct"]).decode("utf-8"))
    except Exception:
        git_timestamp = 0

    info_text = (
        "**__System__**\n"
        f"OS Version: `{platform.system()} {platform.release()}`\n"
        f"Python Version: `{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}`\n"
        f"discord.py Version: `{discord.__version__}{'-catbot' if 'localhost' in str(discord.gateway.DiscordWebSocket.DEFAULT_GATEWAY) else ''}`\n"
        f"CPU usage: `{psutil.cpu_percent():.1f}%`\n"
        f"RAM usage: `{psutil.virtual_memory().percent:.1f}%`\n\n"
        "**__Tech__**\n"
        f"Hard uptime: `{format_timedelta(config.HARD_RESTART_TIME, time.time())}`\n"
        f"Soft uptime: `{format_timedelta(config.SOFT_RESTART_TIME, time.time())}`\n"
        f"Last code update: `{format_timedelta(git_timestamp, time.time()) if git_timestamp else 'N/A'}`\n"
        f"Loops since soft restart: `{loop_count + 1:,}`\n"
        f"Shards: `{len(shared.bot.shards):,}`\n"
        f"Guild shard: `{message.guild.shard_id:,}`\n\n"
        "**__Global Stats__**\n"
        f"Guilds: `{len(shared.bot.guilds):,}`\n"
        f"DB Profiles: `{await Profile.count():,}`\n"
        f"DB Users: `{await User.count():,}`\n"
        f"DB Channels: `{await Channel.count():,}`"
    )

    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(Container(
        "## cattito Info",
        info_text,
        accent_color=Colors.brown,
    ))
    await message.response.send_message(view=view)


@shared.bot.tree.command(description="Confused? Check out the cattito Wiki!")
async def wiki(message: discord.Interaction):
    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(Container(
        "## 📖 cattito Wiki",
        "\n".join([
            "Main Page: https://cattito.fun/",
            "",
            "[cattito](https://cattito.fun/cat-bot)",
            "[Cat Spawning](https://ccattito.fun/spawning)",
            "[Commands](https://cattito.fun/commands)",
            "[Cat Types](https://cattito.fun/cat-types)",
            "[Cattlepass](https://cattito.fun/cattlepass)",
            "[Achievements](https://cattito.fun/achievements)",
            "[Packs](https://cattito.fun/packs)",
            "[Trading](https://cattito.fun/trading)",
            "[Gambling](https://cattito.fun/gambling)",
            "[Catnip](https://cattito.fun/catnip)",
            "[Prisms](https://cattito.fun/prisms)",
        ]),
        accent_color=Colors.brown,
    ))
    await message.response.send_message(view=view)
    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, profile, "wiki")


@shared.bot.tree.command(description="Read The cattito Times™️")
async def news(message: discord.Interaction):
    user = await User.get_or_create(user_id=message.user.id)
    buttons = []
    current_state = user.news_state.strip()

    async def send_news(interaction: discord.Interaction):
        news_id = int(interaction.data["custom_id"])
        if interaction.user != message.user:
            await do_funny(interaction)
            return

        async def go_back(back_interaction: discord.Interaction):
            if back_interaction.user != message.user:
                await do_funny(back_interaction)
                return
            await back_interaction.response.defer()
            await regen_buttons()
            await back_interaction.edit_original_response(view=generate_page(current_page))

        await interaction.response.defer()

        current_state = user.news_state.strip()
        if current_state[news_id] not in "123456789":
            user.news_state = current_state[:news_id] + "1" + current_state[news_id + 1 :]
            await user.save()

        profile = await Profile.get_or_create(guild_id=interaction.guild.id, user_id=interaction.user.id)
        await progress(interaction, profile, "news")

        view = LayoutView(timeout=VIEW_TIMEOUT)
        back_button = Button(emoji="⬅️", label="Back")
        back_button.callback = go_back
        back_row = ActionRow(back_button)

        logging.debug("Read news #%d", news_id)

        if news_id == 0:
            embed = Container(
                "## 💻 Xyron Development Switches to Hetzner!",
                "Exciting update from the dev world! Xyron Development has officially migrated its servers from OVH to **Hetzner** to improve performance and reliability. 🚀\n\nNew server specs:\n- **8 vCPU**\n- **16 GB RAM**\n- **160 GB local disk**\n\nThis upgrade means faster bot response times, smoother dashboard performance, and a more stable experience for everyone using Xyron services. The migration went smoothly, and all systems are online and running perfectly!\n\n-# <t:1738929600:F>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)


        elif news_id == 1:
            embed = Container(
                "## 😸 Mayor Whiskers Declares Nap Day",
                "Attention all felines! Mayor Whiskers has officially declared **Nap Day**. Every cat is encouraged to snooze from dawn till dusk.\n\nSpecial cozy spots have been set up across the city for optimal napping, and purring bonuses may appear randomly for those who nap in style!\n\n-# <t:1738929600:F>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 2:
            embed = Container(
                "## 🎉 Cattito's Kitten Parade Wows the Town",
                "Cattito hosted the annual **Kitten Parade 2024**, and it was a spectacle of whiskers, tails, and tiny paws! Highlights include:\n- 🐾 Over 500 kittens dressed in sparkly hats\n- 🎨 A rainbow cat float\n- 🎶 Live meow-sic from the Cat Band\n\nCitizens lined the streets cheering for the fluffiest parade ever!\n\n-# <t:1738929600:F>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 3:
            embed = Container(
                "## 🌿 Mysterious Catnip Rain Hits the City",
                """Alert, cats! A mysterious catnip rain fell across Cattito this morning. Residents report:\n- Sudden bursts of playful energy\n- 100% increase in zoomies\n- Several cats floating (safely) on giant leaf rafts\n\nAuthorities recommend enjoying the catnip safely and sharing the fun with friends.\n\n-# <t:1738929600:F>""",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 4:
            embed = Container(
                f"## ☕ Cattito Opens the First Feline Café",
                f"""Meowmazing news! Cattito's first-ever **Feline Café** has opened. Menu highlights:\n- Tuna lattes\n- Salmon sushi rolls\n- Catnip tea\n\nEvery visitor gets a complimentary paw print cookie. Special purring spots available for VIP cats.\n\n-# <t:1738929600:F>""",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 5:
            embed = Container(
                "## 🏗️ The Great Cat Tower Construction Begins",
                """Cattito is building the tallest **Cat Tower** ever seen! Details:\n- 12 stories of scratching posts\n- Observation decks on every floor\n- Secret tunnels for adventurous kittens\n\nConstruction will take a few weeks, but the cats are already climbing with excitement!\n\n-# <t:1738929600:F>""",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 6:
            embed = Container(
                "## 🏆 Cattito Wins Best Purring Contest",
                """Purrfection achieved! Cattito has won the **Best Purring Contest** for 2025. Judges were impressed by:\n- 99 dB sustained purring\n- Harmonious vibrato sequences\n- Coordinated group purrs by kittens\n\nCelebratory catnip confetti will be distributed in all participating cities!\n\n-# <t:1738929600:F>""",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 7:
            embed = Container(
                "## 🕵️‍♂️ Adventurous Cat Crew Explores the Attic",
                """Mystery unfolds! The Cattito Adventure Crew ventured into the old attic and discovered:\n- Antique cat toys\n- Forgotten golden yarn balls\n- A tiny secret diary of an ancient feline mayor\n\nExpect exciting new quests inspired by these discoveries soon!\n\n-# <t:1738929600:F>""",
                ActionRow(
                    Button(label="Join the Adventure", url="https://discord.gg/BbDXVm4YTg"),
                ),
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 8:
            embed = Container(
                "## 🎨 Cattito Paints a Giant Mural of Cats",
                """Creative mews! Cattito has painted a giant mural in the city center, featuring:\n- 50 cats doing funny poses\n- Rainbow backgrounds\n- Hidden catnip symbols for the sharp-eyed observer\n\nFans are encouraged to visit and take selfies with their favorite cats in the mural.\n\n-# <t:1738929600:F>""",
                Button(label="View Mural!", disabled=True),
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 9:
            cookie_id = (9, shared.bot.user.id)
            if cookie_id not in temp_cookie_storage.keys():
                cookie_user = await Profile.get_or_create(guild_id=9, user_id=shared.bot.user.id)
                temp_cookie_storage[cookie_id] = cookie_user.cookies

            async def add_yippee(interaction):
                await interaction.response.defer()
                try:
                    temp_cookie_storage[cookie_id] += 1
                except KeyError:
                    cookie_user = await Profile.get_or_create(guild_id=9, user_id=shared.bot.user.id)
                    temp_cookie_storage[cookie_id] = cookie_user.cookies
                await send_yippee(interaction)

            async def send_yippee(interaction):
                view = LayoutView(timeout=VIEW_TIMEOUT)
                btn = Button(label=f"yippee! ({temp_cookie_storage[cookie_id]:,})", emoji=get_emoji("yippee"), style=ButtonStyle.primary)
                btn.callback = add_yippee
                embed = Container(
                    "## cattito is now happy",
                    "thanks for voting",
                    MediaGallery(discord.MediaGalleryItem("https://i.imgur.com/MSZF3ly.png")),
                    "also pls still [go vote](https://top.gg/bot/1387860417706987590/vote)",
                    "===",
                    btn,
                    "-# <t:1757794211>",
                )
                view.add_item(embed)
                view.add_item(back_row)
                await interaction.edit_original_response(view=view)

            await send_yippee(interaction)
        elif news_id == 10:
            embed = Container(
                "## 🐟 Cattito Discovers Magical Fish Pond",
                "Exciting mews! While exploring the enchanted forest, Cattito cats discovered a **Magical Fish Pond** filled with rainbow-colored fish and sparkling water.\n\nCats are mesmerized by the glowing fish, and some even brought tiny leaf boats to float around the pond. Who knows what secrets this magical place holds? 🐾",
                "-# <t:1770000000>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 11:
            embed = Container(
                "## 🦸 New Cat Hero Saves a Lost Kitten",
                "Heroic mews! A brave new cat, known as **Whiskerflash**, rescued a tiny lost kitten from the treetops. 🌳\n\nThe daring rescue included:\n- Scaling the tallest oak\n- Distracting a flock of noisy birds\n- Leading the kitten safely back home\n\nCitizens celebrated with a festival of cat treats and a banner: 'Every Paw Matters!' 🐾",
                "-# <t:1771500000>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 12:
            embed = Container(
                "## 🎭 Cattito Hosts a Fancy Cat Costume Ball",
                "Glamour and whiskers everywhere! The **Fancy Cat Costume Ball** was a roaring success:\n- Cats dressed as tiny royalty, pirates, and superheroes\n- A dance floor made of soft velvet\n- Contest for the fluffiest tail and the fanciest hat\n\nThe ball ended with a glittering fireworks display shaped like fish and yarn balls. Truly a night to remember! ✨",
                "-# <t:1771000000>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)

        elif news_id == 13:
            embed = Container(
                "## 🦸 New Cat Hero Saves a Lost Kitten",
                "Heroic mews! A brave new cat, known as **Whiskerflash**, rescued a tiny lost kitten from the treetops. 🌳\n\nThe daring rescue included:\n- Scaling the tallest oak\n- Distracting a flock of noisy birds\n- Leading the kitten safely back home\n\nCitizens celebrated with a festival of cat treats and a banner: 'Every Paw Matters!' 🐾",
                "-# <t:1771500000>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)


        elif news_id == 14:
            embed = Container(
                "## 🐾 New Commands Drop!",
                "A fresh batch of commands just dropped for everyone to use. Here's the full breakdown:\n\n"
                "**⚔️ `/catfight @user` — Cat Duels**\n"
                "Challenge someone to a proper turn-based cat duel. Your opponent gets a ping with an **Accept** or **Decline** button. Once they accept, you both take turns picking from 6 moves — Scratch, Pounce, Hiss, Sit On, Hairball, and Meow. Crits, stuns, and healing are all in play. Your max HP is based on your collection size, so dedicated collectors hit harder and tank more.\n\n"
                "**🐱 `/howcat` — How Cat Are You?**\n"
                "Generates a percentage rating of how much of a cat you (or someone else) are today. Resets daily.\n\n"
                "**⚖️ `/compare @user` — Head-to-Head Stats**\n"
                "Side-by-side breakdown of your collection vs another user's — total cats, rarity score, and rarest cat owned.\n\n"
                "**🐾 `/catstatus` — What Is Your Cat Doing?**\n"
                "Checks in on your cat and reports their current activity and location. Updates every hour.\n\n"
                "**🎁 `/send @user <type> [amount]` — Gift Cats**\n"
                "Directly transfer cats from your inventory to another user in the same server. Cats are removed from your collection immediately.\n\n"
                "**📊 `/streak` — Streak & Activity Summary**\n"
                "Check your vote streak and a quick overview of your catching activity. Works on other users too.\n\n"
                "-# More to come — go fight someone. 🐾",
                "-# <t:1746316800:F>",
            )
            view.add_item(embed)
            view.add_item(back_row)
            await interaction.edit_original_response(view=view)


    async def regen_buttons():
        nonlocal buttons
        await user.refresh_from_db()
        buttons = []
        current_state = user.news_state.strip()
        for num, article in enumerate(news_list):
            try:
                have_read_this = current_state[num] != "0"
            except Exception:
                have_read_this = False
            button = Button(
                label=article["title"],
                emoji=get_emoji(article["emoji"]),
                custom_id=str(num),
                style=ButtonStyle.green if not have_read_this else ButtonStyle.gray,
            )
            button.callback = send_news
            buttons.append(button)

    await regen_buttons()

    if len(news_list) > len(current_state):
        user.news_state = current_state + "0" * (len(news_list) - len(current_state))
        await user.save()

    current_page = 0

    async def prev_page(interaction):
        nonlocal current_page
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_page -= 1
        await interaction.response.edit_message(view=generate_page(current_page))

    async def next_page(interaction):
        nonlocal current_page
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        current_page += 1
        await interaction.response.edit_message(view=generate_page(current_page))

    async def mark_all_as_read(interaction):
        if interaction.user.id != message.user.id:
            await do_funny(interaction)
            return
        user.news_state = "1" * len(news_list)
        await user.save()
        await regen_buttons()
        await interaction.response.edit_message(view=generate_page(current_page))

    def generate_page(number):
        view = LayoutView(timeout=VIEW_TIMEOUT)
        view.add_item(TextDisplay("Choose an article:"))

        if current_page == 0:
            end = (number + 1) * 4
        else:
            end = len(buttons)
            row = ActionRow()
        for num, button in enumerate(buttons[number * 4 : end]):
            if current_page == 0:
                view.add_item(ActionRow(button))
            else:
                if len(row.children) == 5:
                    view.add_item(row)
                    row = ActionRow()
                row.add_item(button)

        if current_page != 0 and len(row.children) > 0:
            view.add_item(row)

        last_row = ActionRow()

        if current_page != 0:
            button = Button(label="Back")
            button.callback = prev_page
            last_row.add_item(button)

        button = Button(label="Mark all as read")
        button.callback = mark_all_as_read
        last_row.add_item(button)

        if current_page == 0:
            button = Button(label="Archive")
            button.callback = next_page
            last_row.add_item(button)

        view.add_item(last_row)

        return view

    await message.response.send_message(view=generate_page(current_page))
    await achemb(message, "news", "followup")


@shared.bot.tree.command(description="Pong")
async def ping(message: discord.Interaction):
    try:
        latency = round(shared.bot.latency * 1000)
    except Exception:
        latency = "infinite"
    if latency == 0:
        async with aiohttp.ClientSession() as session:
            shard_latency = 0
            try:
                async with session.get("http://localhost:7878/metrics") as response:
                    data = await response.text()
                    total_latencies = 0
                    total_shards = 0
                    for line in data.split("\n"):
                        if line.startswith("gateway_shard_latency{shard="):
                            if "NaN" in line:
                                continue
                            if f'shard="{message.guild.shard_id}"' in line:
                                shard_latency = int(float(line.split(" ")[1]) * 1000)
                            try:
                                total_latencies += float(line.split(" ")[1])
                                total_shards += 1
                            except Exception:
                                pass
                    latency = round((total_latencies / total_shards) * 1000)
            except Exception:
                pass
        postfix = ""
        if shard_latency:
            postfix = f"\nthe neuron for this server has a delay of {shard_latency} ms {get_emoji('staring_cat')}{get_emoji('staring_cat')}"
        await message.response.send_message(f"🏓 cat has global brain delay of {latency} ms {get_emoji('staring_cat')}{postfix}")
    else:
        await message.response.send_message(f"🏓 cat has brain delay of {latency} ms {get_emoji('staring_cat')}")
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    await progress(message, user, "ping")


@shared.bot.tree.command(name="bonus", description="See your active XP bonuses and how to unlock more")
async def bonus_command(message: discord.Interaction):
    await message.response.defer()

    profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=message.user.id)
    global_user = await User.get_or_create(user_id=message.user.id)
    prisms_crafted = await Prism.count("guild_id = $1 AND user_id = $2", message.guild.id, message.user.id)

    bonuses = await get_xp_bonuses(profile, global_user, message.guild, prisms_crafted)
    multiplier = compute_xp_multiplier(bonuses)
    active_count = sum(1 for b in bonuses if b["active"])

    lines = []
    for b in bonuses:
        tick = "✅" if b["active"] else "⬜"
        pct = f"+{round((b['mult'] - 1) * 100):g}%"
        lines.append(f"{tick} {b['emoji']} **{b['label']}** ({pct})\n  ↳ {b['desc']}")

    desc = "\n".join(lines)

    if multiplier > 1.0:
        summary = f"**Current XP multiplier: {multiplier:.2f}x** ({active_count}/{len(bonuses)} bonuses active)"
    else:
        summary = "**No bonuses active yet.** Unlock some to earn more XP from quests!"

    embed = discord.Embed(
        title="⚡ XP Bonuses",
        description=f"{summary}\n\n{desc}",
        color=Colors.yellow if multiplier > 1.0 else Colors.gray,
    )
    embed.set_footer(text="Bonuses stack multiplicatively · Max: 1.95x · Applies to all quest XP")
    await message.followup.send(embed=embed)
