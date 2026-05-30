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
import asyncio, logging, random, time, discord
from discord import ButtonStyle, TextInput, TextStyle
from discord.ui import Button, LayoutView, Modal, Container, Section, TextDisplay, Thumbnail, ActionRow
import shared
import shared
from constants import cattypes, type_dict, allowedemojis, VIEW_TIMEOUT, ach_list, ach_names, ach_titles, pack_data
from core.colors import Colors
from core.utils import get_emoji, do_funny, cat_type_autocomplete, ach_autocomplete
from database import Channel, Profile, Prism, Server, User
from loops.spawning import spawn_cat
from gui.components import Container as CustomContainer, Option, Select


@shared.bot.tree.command(description="(ADMIN) Prevent someone from catching cats for a certain time period")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(person="A person to timeout!", timeout="How many seconds? (0 to reset)")
async def preventcatch(message: discord.Interaction, person: discord.User, timeout: int):
    if timeout < 0:
        await message.response.send_message("uhh i think time is supposed to be a number", ephemeral=True)
        return
    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person.id)
    timestamp = round(time.time()) + timeout
    user.timeout = timestamp
    await user.save()
    await message.response.send_message(
        person.name.replace("_", r"\_") + (f" can't catch cats until <t:{timestamp}:R>" if timeout > 0 else " can now catch cats again.")
    )


@shared.bot.tree.command(description="(ADMIN) Change cattito avatar")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(avatar="The avatar to use (leave empty to reset)")
async def changeavatar(message: discord.Interaction, avatar: Optional[discord.Attachment]):
    await message.response.defer()

    if avatar and avatar.content_type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
        await message.followup.send("Invalid file type! Please upload a PNG, JPEG, GIF, or WebP image.", ephemeral=True)
        return

    if avatar:
        avatar_value = discord.utils._bytes_to_base64_data(await avatar.read())
    else:
        avatar_value = None

    try:
        await shared.bot.http.request(discord.http.Route("PATCH", f"/guilds/{message.guild.id}/members/@me"), json={"avatar": avatar_value})
        await message.followup.send("Avatar changed successfully!")
    except Exception:
        await message.followup.send("Failed to change avatar! Your image is too big or you are changing avatars too quickly.", ephemeral=True)
        return


@shared.bot.tree.command(description="(ADMIN) Change the cat appear timings")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(
    minimum_time="In seconds, minimum possible time between spawns (leave both empty to reset)",
    maximum_time="In seconds, maximum possible time between spawns (leave both empty to reset)",
)
async def changetimings(
    message: discord.Interaction,
    minimum_time: Optional[int],
    maximum_time: Optional[int],
):
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    if not channel:
        await message.response.send_message("This channel isnt setupped. Please select a valid channel.", ephemeral=True)
        return

    if not minimum_time and not maximum_time:
        channel.spawn_times_min = 60
        channel.spawn_times_max = 600
        await channel.save()
        await message.response.send_message("Success! This channel is now reset back to usual spawning intervals.")
    elif minimum_time and maximum_time:
        if minimum_time < 20:
            await message.response.send_message("Sorry, but minimum time must be above 20 seconds.", ephemeral=True)
            return
        if maximum_time < minimum_time:
            await message.response.send_message(
                "Sorry, but maximum time must not be less than minimum time.",
                ephemeral=True,
            )
            return

        channel.spawn_times_min = minimum_time
        channel.spawn_times_max = maximum_time
        await channel.save()

        await message.response.send_message(
            f"Success! The spawn times are now {minimum_time} to {maximum_time} seconds. Please note the changes will only apply after the next spawn."
        )
    else:
        await message.response.send_message("Please input all times.", ephemeral=True)


@shared.bot.tree.command(description="(ADMIN) Change the cat appear and cought messages")
@discord.app_commands.default_permissions(manage_guild=True)
async def changemessage(message: discord.Interaction):
    caller = message.user
    channel = await Channel.get_or_none(channel_id=message.channel.id)
    if not channel:
        await message.response.send_message("pls setup this channel first", ephemeral=True)
        return

    class InputModal(Modal):
        def __init__(self, type):
            super().__init__(
                title=f"Change {type} Message",
                timeout=3600,
            )

            self.type = type

            self.input = TextInput(
                min_length=0,
                max_length=1000,
                label="Input",
                style=discord.TextStyle.long,
                required=False,
                placeholder='{emoji} {type} has appeared! Type "cat" to catch it!',
                default=channel.appear if self.type == "Appear" else channel.cought,
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            await channel.refresh_from_db()
            if not channel:
                await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
                return
            input_value = self.input.value

            if input_value != "":
                check = ["{emoji}", "{type}"] + (["{username}", "{count}", "{time}"] if self.type == "Cought" else [])

                for i in check:
                    if i not in input_value:
                        await interaction.response.send_message(f"nuh uh! you are missing `{i}`.", ephemeral=True)
                        return
                    elif input_value.count(i) > 10:
                        await interaction.response.send_message(f"nuh uh! you are using too much of `{i}`.", ephemeral=True)
                        return

                for i in allowedemojis:
                    if i in input_value:
                        await interaction.response.send_message(f"nuh uh! you cant use `{i}`. sorry!", ephemeral=True)
                        return

                icon = get_emoji("finecat")
                await interaction.response.send_message(
                    "Success! Here is a preview:\n"
                    + input_value.replace("{emoji}", str(icon))
                    .replace("{type}", "Fine")
                    .replace("{username}", "cattito")
                    .replace("{count}", "1")
                    .replace("{time}", "69 years 420 days")
                )
            else:
                await interaction.response.send_message("Reset to defaults.")

            if self.type == "Appear":
                channel.appear = input_value
            else:
                channel.cought = input_value

            await channel.save()

    async def ask_appear(interaction):
        nonlocal caller

        if interaction.user != caller:
            await do_funny(interaction)
            return

        modal = InputModal("Appear")
        await interaction.response.send_modal(modal)

    async def ask_catch(interaction):
        nonlocal caller

        if interaction.user != caller:
            await do_funny(interaction)
            return

        modal = InputModal("Cought")
        await interaction.response.send_modal(modal)

    button1 = Button(label="Appear Message", style=ButtonStyle.blurple)
    button1.callback = ask_appear

    button2 = Button(label="Catch Message", style=ButtonStyle.blurple)
    button2.callback = ask_catch

    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(Container(
        "## ✏️ Change Appear & Catch Messages",
        "Below are buttons to change them. Each message **must** include all required placeholders exactly as shown — cattito will replace them at runtime.\n\n"
        "**Appear message placeholders:**\n`{emoji}`, `{type}`\n\n"
        "**Catch message placeholders:**\n`{emoji}`, `{type}`, `{username}`, `{count}`, `{time}`\n\n"
        "**Mentions:** `@everyone`, `@here`, `<@userid>`, `<@&roleid>`\nRun `/getid` to look up IDs. Make sure the bot has mention permissions.\n\n"
        "Leave input blank to reset to defaults.",
        "===",
        ActionRow(button1, button2),
        accent_color=Colors.brown,
    ))
    await message.response.send_message(view=view)


@shared.bot.tree.command(description="Get ID of a thing")
async def getid(message: discord.Interaction, thing: discord.User | discord.Role):
    await message.response.send_message(f"The ID of {thing.mention} is {thing.id}\nyou can use it in /changemessage like this: `{thing.mention}`")


@shared.bot.tree.command(description="(ADMIN) enable/disable cattito's reactions")
@discord.app_commands.default_permissions(manage_guild=True)
async def togglereactions(message: discord.Interaction):
    server = await Server.get_or_create(server_id=message.guild.id)
    server.do_reactions = not server.do_reactions
    await server.save()
    await message.response.send_message(f"ok, {'enabled' if server.do_reactions else 'disabled'} reactions in this server.")


@shared.bot.tree.command(description="(ADMIN) Give cats to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who", amount="how many (negatives to remove)", cat_type="what")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def givecat(message: discord.Interaction, person_id: discord.User, cat_type: str, amount: Optional[int]):
    if amount is None:
        amount = 1
    if cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    user[f"cat_{cat_type}"] += amount
    await user.save()
    await message.response.send_message(f"gave {person_id.mention} {amount:,} {cat_type} cats", allowed_mentions=discord.AllowedMentions(users=True))


@shared.bot.tree.command(description="(ADMIN) Give packs to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user", pack_type="pack")
@discord.app_commands.describe(
    person_id="Who to give packs to",
    pack_type="Which pack type to give",
    amount="How many packs (negatives to remove)"
)
async def givepacks(
    message: discord.Interaction,
    person_id: discord.User,
    pack_type: Literal["Christmas", "Wooden", "Stone", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Celestial"],
    amount: Optional[int]
):
    if amount is None:
        amount = 1

    INT32_MAX = 2_147_483_647
    if amount < 1 or amount > INT32_MAX:
        await message.response.send_message(
            f"amount must be between 1 and {INT32_MAX:,}", ephemeral=True
        )
        return

    user = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
    pack_field = f"pack_{pack_type.lower()}"
    new_value = user[pack_field] + amount
    if new_value > INT32_MAX:
        new_value = INT32_MAX
    user[pack_field] = new_value
    await user.save()

    pack_emoji = get_emoji(pack_type.lower() + "pack")
    await message.response.send_message(
        f"gave {person_id.mention} {amount:,} {pack_emoji} {pack_type} packs",
        allowed_mentions=discord.AllowedMentions(users=True)
    )


@shared.bot.tree.command(name="setup", description="(ADMIN) Setup cat in current channel")
@discord.app_commands.default_permissions(manage_guild=True)
async def setup_channel(message: discord.Interaction):
    try:
        if isinstance(message.channel, discord.Thread) and not message.channel.parent:
            parent = message.guild.get_channel(message.channel.parent_id) or await message.guild.fetch_channel(message.channel.parent_id)
            channel_permissions = parent.permissions_for(message.guild.me)
        else:
            channel_permissions = message.channel.permissions_for(message.guild.me)
        needed_perms = {
            "View Channel": channel_permissions.view_channel,
            "Send Messages": channel_permissions.send_messages,
            "Attach Files": channel_permissions.attach_files,
        }
        if isinstance(message.channel, discord.Thread):
            needed_perms["Send Messages in Threads"] = channel_permissions.send_messages_in_threads

        for name, value in needed_perms.copy().items():
            if value:
                needed_perms.pop(name)

        missing_perms = list(needed_perms.keys())
        if len(missing_perms) != 0:
            needed_perms = "\n- ".join(missing_perms)
            await message.response.send_message(
                f":x: Missing Permissions! Please give me the following:\n- {needed_perms}\nHint: try setting channel permissions if server ones don't work."
            )
            return

        if await Channel.get_or_none(channel_id=message.channel.id):
            await message.response.send_message(
                "bruh you already setup cat here are you dumb\n\nthere might already be a cat sitting in chat. type `cat` to catch it."
            )
            return

        await Channel.create(channel_id=message.channel.id)
    except Exception:
        await message.response.send_message("this channel gives me bad vibes.")
        return

    await spawn_cat(str(message.channel.id))
    await message.response.send_message(f"ok, now i will also send cats in <#{message.channel.id}>")


@shared.bot.tree.command(description="(ADMIN) Undo the setup")
@discord.app_commands.default_permissions(manage_guild=True)
async def forget(message: discord.Interaction):
    if channel := await Channel.get_or_none(channel_id=message.channel.id):
        await channel.delete()
        await message.response.send_message(f"ok, now i wont send cats in <#{message.channel.id}>")
    else:
        await message.response.send_message("your an idiot there is literally no cat setupped in this channel you stupid")


@shared.bot.tree.command(description="(ADMIN) Force cats to appear")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(cat_type="type")
@discord.app_commands.describe(cat_type="select a cat type ok")
@discord.app_commands.autocomplete(cat_type=cat_type_autocomplete)
async def forcespawn(message: discord.Interaction, cat_type: Optional[str]):
    if cat_type and cat_type not in cattypes:
        await message.response.send_message("bro what", ephemeral=True)
        return

    ch = await Channel.get_or_none(channel_id=message.channel.id)
    if ch is None:
        await message.response.send_message("this channel is not /setup-ed", ephemeral=True)
        return
    if ch.cat:
        await message.response.send_message("there is already a cat", ephemeral=True)
        return
    ch.yet_to_spawn = 0
    await ch.save()
    await spawn_cat(str(message.channel.id), cat_type, True)
    await message.response.send_message("done!\n**Note:** you can use `/givecat` to give yourself cats, there is no need to spam this")


@shared.bot.tree.command(description="(ADMIN) Give achievements to people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user", ach_id="name")
@discord.app_commands.describe(person_id="who", ach_id="name or id of the achievement")
@discord.app_commands.autocomplete(ach_id=ach_autocomplete)
async def giveachievement(message: discord.Interaction, person_id: discord.User, ach_id: str):
    try:
        valid = ach_id in ach_names
    except KeyError:
        valid = False

    if not valid and ach_id.lower() in ach_titles.keys():
        ach_id = ach_titles[ach_id.lower()]
        valid = True

    person = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)

    if valid and ach_id == "thanksforplaying":
        await message.response.send_message("HAHAHHAHAH\nno", ephemeral=True)
        return

    if valid:
        reverse = person[ach_id]
        person[ach_id] = not reverse
        await person.save()
        color, title, icon = (
            Colors.green,
            "Achievement forced!",
            "https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/ach.png",
        )
        if reverse:
            color, title, icon = (
                Colors.red,
                "Achievement removed!",
                "https://wsrv.nl/?url=raw.githubusercontent.com/staring-cat/emojis/main/no_ach.png",
            )
        ach_data = ach_list[ach_id]
        embed = (
            discord.Embed(
                title=ach_data["title"],
                description=ach_data["description"],
                color=color,
            )
            .set_author(name=title, icon_url=icon)
            .set_footer(text=f"for {person_id.name}")
        )
        await message.response.send_message(person_id.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    else:
        await message.response.send_message("i cant find that achievement! try harder next time.", ephemeral=True)


@shared.bot.tree.command(description="(ADMIN) Reset people")
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.rename(person_id="user")
@discord.app_commands.describe(person_id="who")
async def reset(message: discord.Interaction, person_id: discord.User):
    async def confirmed(interaction):
        if interaction.user.id == message.user.id:
            await interaction.response.defer()
            try:
                og = await interaction.original_response()
                profile = await Profile.get_or_create(guild_id=message.guild.id, user_id=person_id.id)
                profile.guild_id = og.id
                await profile.save()
                async for p in Prism.filter("guild_id = $1 AND user_id = $2", message.guild.id, person_id.id):
                    p.guild_id = og.id
                    await p.save()
                await interaction.edit_original_response(
                    content=f"Done! rip {person_id.mention}. f's in chat.\njoin our discord to rollback: <https://discord.gg/BbDXVm4YTg>", view=None
                )
            except Exception:
                await interaction.edit_original_response(
                    content="ummm? this person isnt even registered in cattito wtf are you wiping?????",
                    view=None,
                )
        else:
            await do_funny(interaction)

    view = LayoutView(timeout=VIEW_TIMEOUT)
    button = Button(style=ButtonStyle.red, label="Confirm")
    button.callback = confirmed
    view.add_item(button)
    await message.response.send_message(f"Are you sure you want to reset {person_id.mention}?", view=view, allowed_mentions=discord.AllowedMentions(users=True))


@shared.bot.tree.command(description="(HIGH ADMIN) [VERY DANGEROUS] Reset all cattito data of this server")
@discord.app_commands.default_permissions(administrator=True)
async def nuke(message: discord.Interaction):
    warning_text = "⚠️ This will completely reset **all** cattito progress of **everyone** in this server. Spawn channels and their settings *will not be affected*.\nPress the button 5 times to continue."
    counter = 5

    async def gen(counter):
        lines = [
            "",
            "I'm absolutely sure! (1)",
            "I understand! (2)",
            "You can't undo this! (3)",
            "This is dangerous! (4)",
            "Reset everything! (5)",
        ]
        view = LayoutView(timeout=VIEW_TIMEOUT)
        button = Button(label=lines[max(1, counter)], style=ButtonStyle.red)
        button.callback = count
        view.add_item(button)
        return view

    async def count(interaction: discord.Interaction):
        nonlocal message, counter
        if interaction.user.id == message.user.id:
            await interaction.response.defer()
            counter -= 1
            if counter == 0:
                changed_profiles = []
                changed_prisms = []

                async for i in Profile.filter("guild_id = $1", message.guild.id):
                    i.guild_id = interaction.message.id
                    changed_profiles.append(i)

                async for i in Prism.filter("guild_id = $1", message.guild.id):
                    i.guild_id = interaction.message.id
                    changed_prisms.append(i)

                if changed_profiles:
                    await Profile.bulk_update(changed_profiles, "guild_id")
                if changed_prisms:
                    await Prism.bulk_update(changed_prisms, "guild_id")
                await Profile.create(guild_id=interaction.message.id, user_id=0)

                try:
                    await interaction.edit_original_response(
                        content="Done. If you want to roll this back, please contact us in our discord: <https://discord.gg/BbDXVm4YTg>.",
                        view=None,
                    )
                except Exception:
                    await interaction.followup.send("Done. If you want to roll this back, please contact us in our discord: <https://discord.gg/BbDXVm4YTg>.")
            else:
                view = await gen(counter)
                try:
                    await interaction.edit_original_response(content=warning_text, view=view)
                except Exception:
                    pass
        else:
            await do_funny(interaction)

    view = await gen(counter)
    await message.response.send_message(warning_text, view=view)
