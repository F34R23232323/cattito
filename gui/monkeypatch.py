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
from discord.ui import LayoutView, ActionRow, Container, TextDisplay

# Keep references to originals in case we need them
_ORIG_SEND = discord.abc.Messageable.send
_ORIG_EDIT = discord.Message.edit
_ORIG_WEBHOOK_EDIT = discord.WebhookMessage.edit
_ORIG_INTERACTION_SEND = discord.InteractionResponse.send_message
_ORIG_INTERACTION_EDIT = discord.InteractionResponse.edit_message
_ORIG_WEBHOOK_SEND = discord.Webhook.send
_ORIG_LAYOUT_ADD_ITEM = LayoutView.add_item

_MISSING = discord.utils.MISSING
_orig_send = _ORIG_SEND
_orig_edit = _ORIG_EDIT
_orig_webhook_edit = _ORIG_WEBHOOK_EDIT
_orig_interaction_send = _ORIG_INTERACTION_SEND
_orig_interaction_edit = _ORIG_INTERACTION_EDIT
_orig_webhook_send = _ORIG_WEBHOOK_SEND
_orig_layout_add_item = _ORIG_LAYOUT_ADD_ITEM

from gui.containers import embed_to_container

_ORIG_SECTION_INIT = discord.ui.Section.__init__
_ORIG_CONTAINER_INIT = discord.ui.Container.__init__


def _v2_section_init(self, *children, **kwargs):
    if "accessory" not in kwargs:
        acc = None
        new_children = []
        for child in children:
            if isinstance(child, (discord.ui.Button, discord.ui.Thumbnail)):
                acc = child
            else:
                new_children.append(child)
        if acc is None:
            acc = discord.ui.TextDisplay("")
        _ORIG_SECTION_INIT(self, *new_children, accessory=acc, **{k: v for k, v in kwargs.items() if k != "accessory"})
    else:
        _ORIG_SECTION_INIT(self, *children, **kwargs)


def _v2_container_init(self, *children, **kwargs):
    if "accent_color" not in kwargs and "accent_colour" not in kwargs:
        kwargs["accent_color"] = 0x6E593C  # Colors.brown
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
    _ORIG_CONTAINER_INIT(self, *new_children, **kwargs)


async def _v2_send(self, content=_MISSING, *, embed=_MISSING, embeds=_MISSING, view=_MISSING, file=_MISSING, files=_MISSING, **kwargs):
    if isinstance(view, LayoutView) and embed is not _MISSING and embed is not None:
        container = embed_to_container(embed)
        view.add_item(container)
        embed = _MISSING
    if isinstance(view, LayoutView) and content is not _MISSING and content is not None:
        container = Container(TextDisplay(content), accent_color=None)
        view.add_item(container)
        content = _MISSING
    call_kwargs = kwargs.copy()
    if content is not _MISSING: call_kwargs['content'] = content
    if embed is not _MISSING: call_kwargs['embed'] = embed
    if embeds is not _MISSING: call_kwargs['embeds'] = embeds
    if view is not _MISSING: call_kwargs['view'] = view
    if file is not _MISSING: call_kwargs['file'] = file
    if files is not _MISSING: call_kwargs['files'] = files
    return await _orig_send(self, **call_kwargs)


async def _v2_edit(self, *, content=_MISSING, embed=_MISSING, embeds=_MISSING, view=_MISSING, **kwargs):
    if isinstance(view, LayoutView) and embed is not _MISSING and embed is not None:
        container = embed_to_container(embed)
        view.add_item(container)
        embed = _MISSING
    if isinstance(view, LayoutView) and content is not _MISSING and content is not None:
        container = Container(TextDisplay(content), accent_color=None)
        view.add_item(container)
        content = _MISSING
    call_kwargs = kwargs.copy()
    if content is not _MISSING: call_kwargs['content'] = content
    if embed is not _MISSING: call_kwargs['embed'] = embed
    if embeds is not _MISSING: call_kwargs['embeds'] = embeds
    if view is not _MISSING: call_kwargs['view'] = view
    return await _orig_edit(self, **call_kwargs)


async def _v2_webhook_edit(self, *, content=_MISSING, embed=_MISSING, embeds=_MISSING, view=_MISSING, **kwargs):
    if isinstance(view, LayoutView) and embed is not _MISSING and embed is not None:
        container = embed_to_container(embed)
        view.add_item(container)
        embed = _MISSING
    if isinstance(view, LayoutView) and content is not _MISSING and content is not None:
        container = Container(TextDisplay(content), accent_color=None)
        view.add_item(container)
        content = _MISSING
    call_kwargs = kwargs.copy()
    if content is not _MISSING: call_kwargs['content'] = content
    if embed is not _MISSING: call_kwargs['embed'] = embed
    if embeds is not _MISSING: call_kwargs['embeds'] = embeds
    if view is not _MISSING: call_kwargs['view'] = view
    return await _orig_webhook_edit(self, **call_kwargs)


async def _v2_interaction_send(self, content=_MISSING, *, embed=_MISSING, embeds=_MISSING, view=_MISSING, **kwargs):
    if isinstance(view, LayoutView) and embed is not _MISSING and embed is not None:
        container = embed_to_container(embed)
        view.add_item(container)
        embed = _MISSING
    if isinstance(view, LayoutView) and content is not _MISSING and content is not None:
        container = Container(TextDisplay(content), accent_color=None)
        view.add_item(container)
        content = _MISSING
    call_kwargs = kwargs.copy()
    if content is not _MISSING: call_kwargs['content'] = content
    if embed is not _MISSING: call_kwargs['embed'] = embed
    if embeds is not _MISSING: call_kwargs['embeds'] = embeds
    if view is not _MISSING: call_kwargs['view'] = view
    return await _orig_interaction_send(self, **call_kwargs)


async def _v2_interaction_edit(self, *, content=_MISSING, embed=_MISSING, embeds=_MISSING, view=_MISSING, **kwargs):
    if isinstance(view, LayoutView) and embed is not _MISSING and embed is not None:
        container = embed_to_container(embed)
        view.add_item(container)
        embed = _MISSING
    if isinstance(view, LayoutView) and content is not _MISSING and content is not None:
        container = Container(TextDisplay(content), accent_color=None)
        view.add_item(container)
        content = _MISSING
    call_kwargs = kwargs.copy()
    if content is not _MISSING: call_kwargs['content'] = content
    if embed is not _MISSING: call_kwargs['embed'] = embed
    if embeds is not _MISSING: call_kwargs['embeds'] = embeds
    if view is not _MISSING: call_kwargs['view'] = view
    return await _orig_interaction_edit(self, **call_kwargs)


async def _v2_webhook_send(self, content=_MISSING, *, embed=_MISSING, embeds=_MISSING, view=_MISSING, **kwargs):
    if isinstance(view, LayoutView) and embed is not _MISSING and embed is not None:
        container = embed_to_container(embed)
        view.add_item(container)
        embed = _MISSING
    if isinstance(view, LayoutView) and content is not _MISSING and content is not None:
        container = Container(TextDisplay(content), accent_color=None)
        view.add_item(container)
        content = _MISSING
    call_kwargs = kwargs.copy()
    if content is not _MISSING: call_kwargs['content'] = content
    if embed is not _MISSING: call_kwargs['embed'] = embed
    if embeds is not _MISSING: call_kwargs['embeds'] = embeds
    if view is not _MISSING: call_kwargs['view'] = view
    return await _orig_webhook_send(self, **call_kwargs)


def _v2_layout_add_item(self, item):
    if isinstance(item, (discord.ui.Button, discord.ui.Select)) and not isinstance(item, ActionRow):
        item = ActionRow(item)
    return _orig_layout_add_item(self, item)


def apply_monkeypatches():
    """Apply all the Discord.py monkey-patches for LayoutView container support."""
    discord.abc.Messageable.send = _v2_send
    discord.Message.edit = _v2_edit
    discord.WebhookMessage.edit = _v2_webhook_edit
    discord.InteractionResponse.send_message = _v2_interaction_send
    discord.InteractionResponse.edit_message = _v2_interaction_edit
    discord.Webhook.send = _v2_webhook_send
    LayoutView.add_item = _v2_layout_add_item
    discord.ui.Section.__init__ = _v2_section_init
    discord.ui.Container.__init__ = _v2_container_init
