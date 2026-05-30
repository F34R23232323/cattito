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

import asyncio, logging, random
import discord
from core.colors import Colors
from core.utils import get_emoji
from constants import cattypes, catnip_list
from database import Profile


async def get_perks(level, user):
    level_data = catnip_list["levels"][level]
    rarities = [r for r in level_data["weights"].keys()]
    weights = {rarity: level_data["weights"][rarity] for rarity in rarities}
    perks = catnip_list["perks"]

    current_perks = []
    used_ids = set()
    thelist = []
    if user.perks:
        for perk in user.perks:
            p = perk.split("_")
            thelist.append(perks[int(p[1]) - 1]["id"])

    for _ in range(3):
        luck = random.randint(1, 1000) / 10
        total_weight = 0
        current_rarity = "common"
        for rarity, weight in weights.items():
            total_weight += weight
            if luck <= total_weight:
                current_rarity = rarity
                break

        tries = 0
        selected_perk = None

        while tries < 100:
            luck = random.randint(1, 100)
            total_weight = 0
            i = 0
            for perk in perks:
                i += 1
                total_weight += perk["weight"]

                if perk["id"] in used_ids or (perk["exclusive"] == 1 and perk["id"] in thelist):
                    continue

                if all("pack" in p["id"] for p in current_perks) and "pack" in perk["id"]:
                    continue

                if luck <= total_weight:
                    effect = perk["values"][list(weights.keys()).index(current_rarity)]
                    if effect == 0:
                        continue

                    selected_perk = {
                        "id": perk["id"],
                        "name": perk["name"],
                        "values": perk["values"],
                        "rarity": current_rarity,
                        "uuid": f"{list(weights.keys()).index(current_rarity)}_{i}",
                        "effect": effect,
                    }

                    break
            if selected_perk:
                break
            tries += 1

        if selected_perk:
            used_ids.add(selected_perk["id"])
            current_perks.append(selected_perk)

    return current_perks


async def level_down(user, message, ephemeral=False):
    if user.catnip_level == 0:
        return

    user.catnip_level -= 1
    user.catnip_active = 0

    user.hibernation = True

    for number in ["one", "two", "three"]:
        user[f"bounty_id_{number}"] = 0
        user[f"bounty_type_{number}"] = ""
        user[f"bounty_total_{number}"] = 1
        user[f"bounty_progress_{number}"] = 0

    user.catnip_total_cats = 0

    user.bounty_active = False
    user.first_quote_seen = False

    if user.perks:
        h = list(user.perks)
        removed_perk = h.pop()
        user.perks = h[:]

    await set_bounties(user.catnip_level, user)
    await set_mafia_offer(user.catnip_level, user)
    await user.save()

    name = catnip_list["quotes"][user.catnip_level]["name"]
    quote = catnip_list["quotes"][user.catnip_level]["quotes"]["leveldown"].replace("jeremysus", get_emoji("jeremysus"))
    removed_line = ""

    if user.perks and removed_perk:
        rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        perk_rarity = int(removed_perk.split("_")[0])
        perk_type = int(removed_perk.split("_")[1])
        perk_data = catnip_list["perks"][perk_type - 1]

        removed_line = f"\nYou lost your **{perk_data['name']} ({rarities[perk_rarity]})** perk."

    embed = discord.Embed(
        title="❌ Mafia Level Failed",
        color=Colors.red,
        description=f"**{name}**: *{quote}*\n\nLevel {user.catnip_level + 1} bounties failed!\nYou're now on level {user.catnip_level}.{removed_line}",
    )

    logging.debug("Levelled down to %d", user.catnip_level)

    if ephemeral:
        return embed

    await message.channel.send(f"<@{user.user_id}>", embed=embed)
