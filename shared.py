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
import time

import discord
from discord.ext import commands


class _BotProxy:
    """Proxy wrapper that delegates all attribute access to the real bot.
    Allows `from shared import bot` to always resolve to the current bot
    even after `shared.bot = real_bot` replaces the placeholder."""

    __slots__ = ("_real",)

    def __init__(self, bot):
        object.__setattr__(self, "_real", bot)

    def _set(self, bot):
        object.__setattr__(self, "_real", bot)

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        object.__setattr__(self._real, name, value)

    def __delattr__(self, name):
        object.__delattr__(self._real, name)

    def __repr__(self):
        return repr(self._real)

    def __eq__(self, other):
        if isinstance(other, _BotProxy):
            return self._real == other._real
        return self._real == other

    def __hash__(self):
        return hash(self._real)


# Placeholder bot — replaced at runtime by setup() in main.py
_placeholder = commands.AutoShardedBot(
    command_prefix="this is a placebo bot which will be replaced when this will get loaded",
    intents=discord.Intents.default(),
)

bot = _BotProxy(_placeholder)

vote_server = None

_ac_data: dict[int, dict] = {}

temp_catches_storage: list = []
temp_spawns_storage: list = []
temp_belated_storage: dict = {}
temp_cookie_storage: dict = {}

on_ready_debounce = False

about_to_stop = False

emojis: dict = {}

RAIN_ID = 1270470307102195752

OWNER_IDS = {
    1075077561454973020,
    952009664600608808,
    1296592197260415057,
    579080596723335181,
}

loop_count = 0
last_loop_time = 0

reactions_ratelimit: dict = {}
pointlaugh_ratelimit: dict = {}

catchcooldown: dict = {}
fakecooldown: dict = {}
customcatcooldown: dict = {}

pending_votes: list = []

casino_lock: list = []
slots_lock: list = []

rigged_users: list = []

gen_credits: dict[str, str] = {}

_webhook_log_handler = None
