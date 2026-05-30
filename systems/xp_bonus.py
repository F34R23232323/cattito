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

from core.utils import get_emoji

NOXX_ID = 1370898570403647528


async def get_xp_bonuses(profile, global_user, guild, prisms_crafted: int) -> list:
    bonuses = []

    noxx_here = guild is not None and guild.get_member(NOXX_ID) is not None
    bonuses.append({
        "mult": 1.5, "label": "Noxx Neighbour", "emoji": "\U0001f91d",
        "desc": "Add Noxx to this server", "active": noxx_here,
    })

    streak = getattr(global_user, "vote_streak", 0) or 0
    bonuses.append({
        "mult": 1.1, "label": "Loyal Voter", "emoji": "\U0001f5f3\ufe0f",
        "desc": f"Maintain a 7-day vote streak ({streak}/7)", "active": streak >= 7,
    })

    quests = getattr(profile, "quests_completed", 0) or 0
    bonuses.append({
        "mult": 1.1, "label": "Quest Grinder", "emoji": "\U0001f4dc",
        "desc": f"Complete 50 quests in this server ({quests}/50)", "active": quests >= 50,
    })

    bonuses.append({
        "mult": 1.1, "label": "Prism Holder", "emoji": get_emoji("prism"),
        "desc": f"Craft at least 1 prism in this server ({prisms_crafted}/1)", "active": prisms_crafted >= 1,
    })

    catches = getattr(profile, "total_catches", 0) or 0
    bonuses.append({
        "mult": 1.1, "label": "Serial Catcher", "emoji": "\U0001f43e",
        "desc": f"Catch 500 cats in this server ({catches}/500)", "active": catches >= 500,
    })

    bp_level = getattr(profile, "battlepass", 0) or 0
    bonuses.append({
        "mult": 1.1, "label": "Battlepass Beast", "emoji": "\u2b50",
        "desc": f"Reach battlepass level 20 this season ({bp_level}/20)", "active": bp_level >= 20,
    })

    return bonuses


def compute_xp_multiplier(bonuses: list) -> float:
    total = 1.0
    for b in bonuses:
        if b["active"]:
            total *= b["mult"]
    return min(round(total, 4), 1.95)
