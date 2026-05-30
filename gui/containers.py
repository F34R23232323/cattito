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
from discord.ui import Thumbnail, TextDisplay, Section, Container


def embed_to_container(embed: discord.Embed) -> Container:
    children = []

    if embed.title:
        title_text = f"## {embed.title}"
        if embed.url:
            title_text = f"## [{embed.title}]({embed.url})"
        children.append(title_text)

    if embed.description:
        children.append(embed.description)

    field_texts = []
    for field in embed.fields:
        field_texts.append(f"**{field.name}**\n{field.value}")
    if field_texts:
        children.append("\n".join(field_texts))

    if embed.image and embed.image.url:
        children.append(embed.image.url)

    if embed.footer and embed.footer.text:
        footer_text = embed.footer.text
        if embed.timestamp:
            footer_text += f" | {embed.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        children.append(f"-# {footer_text}")

    if not children:
        return Container(accent_color=embed.color if embed.color else None)

    content = "\n\n".join(children)
    if embed.thumbnail and embed.thumbnail.url:
        section = Section(
            TextDisplay(content),
            Thumbnail(embed.thumbnail.url)
        )
        return Container(section, accent_color=embed.color if embed.color else None)
    else:
        return Container(
            TextDisplay(content),
            accent_color=embed.color if embed.color else None
        )
