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
import discord
from discord import ButtonStyle
from discord.ui import Button, LayoutView
from constants import VIEW_TIMEOUT
from core.colors import Colors
from database import Profile
from achievements import achemb


async def mafia_cutscene(interaction: discord.Interaction, user):
    text1 = """You feel satisfied with yourself. I just defeated the Godfather, Bailey! I'm on top of the world now!
Little did you know, it was foolish to believe it was over just yet.
You stare Bailey down, and realize just how bizarre he is. He's very large for a cat\u2026 he wags his tail\u2026 he just feels wrong. But then, you hear it.
*Bark! Bark!*
Oh no."""
    text2 = """You immediately run. You know that he will probably be able to outpace you, but you do have a bit of a head start.
There's a split in the alley.
Left would lead to the hideout, but you'll never get there in time.
Right, however, leads to a dead end.
Which way do you go?"""
    text3a = """You dash to the left. You can see the cat door ahead, but you'll never make it out in time.
You call out for help, and think back to all of those people you defeated.
Whiskers, the Lucians, Jinx, Jeremy, Sofia.
Would any of them be willing to save you?"""
    text3b = """You dash to the right. As you turn the corner and approach the dead end, you realize that while he may go faster, you can jump higher.
You back up against the wall, wait for him to approach\u2026 and jump.
You get over him, and run the other way. With a head start, you can get into the hideout.
But Bailey isn't done yet.
He's trying to break in. You think back to all of those people you defeated.
Whiskers, the Lucians, Jinx, Jeremy, Sofia.
Would any of them be willing to save you?"""
    text4 = """You see Jinx come out first. Whiskers is just behind him.
Jeremy doesn't take much longer. The Lucians come out too, though reluctantly.
Finally, Sofia scowls and approaches.
Bailey knew he could take down one cat. Two wouldn't be that hard. But seven..?
\"This isn't the end of this...\"
Bailey puts his head down, and scampers off. But you aren't done.
You and your crew chase after him. He runs, until you corner him. He goes into the building behind him\u2026 but it's the Cat Police Station.
As you return to your hideout, you hear a howl in the distance."""

    async def button3_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(content=text4, view=None)
        user.thanksforplaying = False
        user.cutscene = 1
        await user.save()
        await achemb(interaction, "thanksforplaying", "followup")

    async def button2a_callback(interaction: discord.Interaction):
        myview3 = LayoutView(timeout=VIEW_TIMEOUT)
        button3 = Button(label="Next", style=ButtonStyle.blurple)
        button3.callback = button3_callback
        myview3.add_item(button3)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text3a, view=myview3)

    async def button2b_callback(interaction: discord.Interaction):
        myview3 = LayoutView(timeout=VIEW_TIMEOUT)
        button3 = Button(label="Next", style=ButtonStyle.blurple)
        button3.callback = button3_callback
        myview3.add_item(button3)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text3b, view=myview3)

    async def button1_callback(interaction: discord.Interaction):
        myview2 = LayoutView(timeout=VIEW_TIMEOUT)
        button2a = Button(label="Left", style=ButtonStyle.red)
        button2b = Button(label="Right", style=ButtonStyle.green)
        button2a.callback = button2a_callback
        button2b.callback = button2b_callback
        myview2.add_item(button2a)
        myview2.add_item(button2b)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text2, view=myview2)

    user.thanksforplaying = True
    await user.save()

    myview1 = LayoutView(timeout=VIEW_TIMEOUT)
    button1 = Button(label="RUN!", style=ButtonStyle.blurple)
    button1.callback = button1_callback
    myview1.add_item(button1)
    await interaction.followup.send(content=text1, view=myview1, ephemeral=True)


async def mafia_cutscene2(interaction: discord.Interaction, user):
    text1 = """Why? What do you gain from this? What's the point?
You've gone too far. You defeated Bailey, and I was proud of you for that.
But you kept going. Just for slightly more cats.
You never cared about the people. It was all for you."""
    text2 = """I got too greedy myself. I took over the mafia far too young.
I wanted more, and more, and more. But I never went as far as you did.
I took over catnip production, and took so much for myself.
Eventually, though, someone took away my catnip.
And I realized how I had taken so much catnip, that the whole world was limited to about 4 doses a week."""
    text3 = """But you. You've left nothing for the others. You've made the most powerful catnip, but at what cost?
I can't stop you. No one can. I guess the only question is: will you stay here to torment us? Or fight on, against the world itself?
[More content coming soon! Congrats on actually making it to level 10, that's quite a feat.]"""
    text4a = """...Really? I thought you would continue your path of destruction.
So fine. Continue to torment us. You've won. Are you happy now?"""
    text4b = """woa you looked at the code! crazy. btw stella is cute"""

    async def button3a_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(content=text4a, view=None)
        user.mafia_win = False
        user.cutscene = 2
        await user.save()
        await achemb(interaction, "mafia_win", "followup")

    async def button3b_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(content=text4b, view=None)

    async def button2_callback(interaction: discord.Interaction):
        myview3 = LayoutView(timeout=VIEW_TIMEOUT)
        button3a = Button(label="Stay", style=ButtonStyle.green)
        button3b = Button(label="Continue", style=ButtonStyle.red, disabled=True)
        button3a.callback = button3a_callback
        button3b.callback = button3b_callback
        myview3.add_item(button3a)
        myview3.add_item(button3b)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text3, view=myview3)

    async def button1_callback(interaction: discord.Interaction):
        myview2 = LayoutView(timeout=VIEW_TIMEOUT)
        button2 = Button(label="Next", style=ButtonStyle.blurple)
        button2.callback = button2_callback
        myview2.add_item(button2)
        await interaction.response.defer()
        await interaction.edit_original_response(content=text2, view=myview2)

    user.mafia_win = True
    await user.save()

    myview1 = LayoutView(timeout=VIEW_TIMEOUT)
    button1 = Button(label="'uhhhh'", style=ButtonStyle.blurple)
    button1.callback = button1_callback
    myview1.add_item(button1)
    await interaction.followup.send(content=text1, view=myview1, ephemeral=True)
