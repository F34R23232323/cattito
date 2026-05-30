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

import discord

from core.colors import Colors


class Option:
    def __init__(self, label, emoji, description=None, value=None):
        self.label = label
        self.emoji = emoji
        self.value = value if value is not None else label
        self.description = description


class Select(discord.ui.Select):
    on_select = None

    def __init__(
        self,
        id: str,
        placeholder: str,
        opts: list[Option],
        selected: str = None,
        on_select: callable = None,
        disabled: bool = False,
    ):
        options = []
        if on_select is not None:
            self.on_select = on_select

        for opt in opts:
            options.append(discord.SelectOption(label=opt.label, description=opt.description, value=opt.value, emoji=opt.emoji, default=opt.value == selected))

        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id=id,
            max_values=1,
            min_values=1,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.on_select is not None and callable(self.on_select):
            await self.on_select(interaction, self.values[0])


class Container(discord.ui.Container):
    def __init__(self, *children, **kwargs):
        if "accent_color" not in kwargs:
            kwargs["accent_color"] = Colors.brown

        new_children = []

        for child in children:
            if isinstance(child, str):
                if child == "===":
                    new_children.append(discord.ui.Separator())
                else:
                    new_children.append(discord.ui.TextDisplay(child))
            elif isinstance(child, discord.ui.Button):
                new_children.append(discord.ui.ActionRow(child))
            else:
                new_children.append(child)

        super().__init__(*new_children, **kwargs)


class Section(discord.ui.Section):
    def __init__(self, *children, **kwargs):
        if "accessory" not in kwargs:
            acc = None
            new_children = []
            for child in children:
                if isinstance(child, discord.ui.Button) or isinstance(child, discord.ui.Thumbnail):
                    acc = child
                else:
                    new_children.append(child)
            if acc is None:
                acc = discord.ui.TextDisplay("")
            kwargs["accessory"] = acc
            super().__init__(*new_children, **kwargs)
        else:
            super().__init__(*children, **kwargs)
