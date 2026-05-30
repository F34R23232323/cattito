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

import asyncio, logging, math, random
import discord
from core.colors import Colors
from core.utils import get_emoji
from constants import cattypes, type_dict, catnip_list
from database import Profile
from achievements import achemb


async def bounty(message, user, cattype):
    if user.hibernation:
        return
    complete = 0
    completed = 0
    title = []
    colored = 0
    for i in range(user.bounties):
        if i == 0:
            id = user.bounty_id_one
            progress = user.bounty_progress_one
            total = user.bounty_total_one
            type = user.bounty_type_one
        if i == 1:
            id = user.bounty_id_two
            progress = user.bounty_progress_two
            total = user.bounty_total_two
            type = user.bounty_type_two
        if i == 2:
            id = user.bounty_id_three
            progress = user.bounty_progress_three
            total = user.bounty_total_three
            type = user.bounty_type_three
        if progress < total:
            if id == 0:
                progress += 1
                if progress == total:
                    complete += 1
                    title.append(f"Catch {total} cats")
            if id == 1:
                if cattype == type:
                    progress += 1
                    if progress == total:
                        complete += 1
                        title.append(f"Catch {total} {type} cats")
            if id == 2:
                if cattypes.index(cattype) >= cattypes.index(type):
                    progress += 1
                    if progress == total:
                        complete += 1
                        title.append(f"Catch {total} {type} or rarer cats")
        if i == 0:
            user.bounty_progress_one = progress
            if progress == total:
                completed += 1
        if i == 1:
            user.bounty_progress_two = progress
            if progress == total:
                completed += 1
        if i == 2:
            user.bounty_progress_three = progress
            if progress == total:
                completed += 1
        colored += (progress / total) * 10 / user.bounties
        await user.save()
    if catnip_list["levels"][user.catnip_level]["bonus"]:
        bonus_title = ""
        if user.bounty_progress_bonus < user.bounty_total_bonus:
            if user.bounty_id_bonus == 0:
                user.bounty_progress_bonus += 1
                bonus_title = f"Catch {user.bounty_total_bonus} cats"
            elif user.bounty_id_bonus == 1:
                if cattype == user.bounty_type_bonus:
                    user.bounty_progress_bonus += 1
                bonus_title = f"Catch {user.bounty_total_bonus} {cattype} cats"
            else:
                if cattypes.index(cattype) >= cattypes.index(user.bounty_type_bonus):
                    user.bounty_progress_bonus += 1
                bonus_title = f"Catch {user.bounty_total_bonus} {user.bounty_type_bonus} or rarer cats"
            if user.bounty_progress_bonus == user.bounty_total_bonus:
                description = "Bonus Bounty Complete!\nGo to `/catnip` to reroll a perk!"
                embed = discord.Embed(title=f"✅ {bonus_title}", color=Colors.green, description=description).set_author(
                    name="Mafia Level " + str(user.catnip_level)
                )
                await message.channel.send(f"<@{user.user_id}>", embed=embed)
                user.reroll = False
                user.reroll_level = 0
            await user.save()
    for i in range(complete):
        logging.debug("Completed bounties %d", completed)
        level = user.catnip_level
        progress_line = f"\n{level} " + get_emoji("staring_square") * int(colored) + "⬛" * int(10 - colored) + f" {level + 1}"
        if completed == user.bounties:
            description = f"{progress_line}\nAll Bounties Complete!\nGo to `/catnip` to pay up and pick a perk!"
        else:
            description = f"{progress_line}\n{completed}/{user.bounties} Bounties Complete"
        embed = discord.Embed(title=f"✅ {title[i]}", color=Colors.green, description=description).set_author(name="Mafia Level " + str(level))
        user.bounties_complete += 1
        if user.bounties_complete >= 5:
            await achemb(message, "bounty_novice", "followup")
        if user.bounties_complete >= 19:
            await achemb(message, "bounty_hunter", "followup")
        if user.bounties_complete >= 100:
            await achemb(message, "bounty_lord", "followup")
        await message.channel.send(f"<@{user.user_id}>", embed=embed)
        await user.save()


async def set_mafia_offer(level, user):
    if user.catnip_level == 0:
        user.catnip_amount = 0
        user.catnip_rain_reward = 0
        return
    level_data = catnip_list["levels"][level]
    vt = level_data["cost"]
    cattype = "Fine"
    for _ in range(100):
        cattype = random.choice(cattypes)
        value = sum(type_dict.values()) / type_dict[cattype]
        if value <= vt:
            break
    amount = max(1, round(vt / value))
    user.catnip_price = cattype
    user.catnip_amount = amount
    user.catnip_rain_reward = max(1, level // 2)
    await user.save()


async def set_bounties(level, user):
    if user.catnip_level == 0:
        user.bounties = 0
        return
    bounties = await get_bounties(level)
    bonus_check = catnip_list["levels"][level + 1]["bonus"]
    if level == 10 and user.bounty_progress_bonus != user.bounty_total_bonus and user.catnip_active > 86400:
        bonus_check = False
    if bonus_check:
        bonus = bounties.pop()
        user.bounty_id_bonus = bonus["id"]
        user.bounty_type_bonus = bonus["cat_type"]
        user.bounty_total_bonus = bonus["amount"]
        user.bounty_progress_bonus = bonus["progress"]
    else:
        bounties = bounties[:-1]
    user.bounties = len(bounties)

    user.bounty_id_one = bounties[0]["id"] if bounties else None
    user.bounty_id_two = bounties[1]["id"] if len(bounties) > 1 else None
    user.bounty_id_three = bounties[2]["id"] if len(bounties) > 2 else None

    user.bounty_type_one = bounties[0]["cat_type"] if bounties else None
    user.bounty_type_two = bounties[1]["cat_type"] if len(bounties) > 1 else None
    user.bounty_type_three = bounties[2]["cat_type"] if len(bounties) > 2 else None

    user.bounty_total_one = bounties[0]["amount"] if bounties else 1
    user.bounty_total_two = bounties[1]["amount"] if len(bounties) > 1 else 1
    user.bounty_total_three = bounties[2]["amount"] if len(bounties) > 2 else 1

    user.bounty_progress_one = bounties[0]["progress"] if bounties else 0
    user.bounty_progress_two = bounties[1]["progress"] if len(bounties) > 1 else 0
    user.bounty_progress_three = bounties[2]["progress"] if len(bounties) > 2 else 0

    await user.save()


async def get_bounties(level):
    level_data = catnip_list["levels"][level + 1]
    bounties = []
    num_bounties = level_data["bounty_amount"]
    avg_cats_needed = level_data["bounty_difficulty"]
    num_max = level_data["max_amount"]

    used_types = set()
    used_rarities = set()
    tries = 0
    max_tries = 1000 * num_bounties
    while len(bounties) < num_bounties + 1 and tries < max_tries:
        tries += 1
        bounty_type = random.choice(["rarity", "specific", "any"])

        variation = random.uniform(0.85, 1.15)
        if len(bounties) == num_bounties:
            variation *= 1.5
            if level == 10:
                variation *= 10
        if bounty_type == "rarity":
            margin = 0.2
            rarity_i = random.randint(2, len(cattypes) - 2)

            while True:
                rarity = cattypes[rarity_i]
                eligible_types = cattypes[rarity_i:]

                prob = sum(type_dict[t] for t in eligible_types) / sum(type_dict.values())
                base_amount = max(1, round(avg_cats_needed * prob))
                expected_total = base_amount / prob if prob > 0 else float("inf")

                if abs(expected_total - avg_cats_needed) / avg_cats_needed <= margin or rarity_i == 0:
                    break
                rarity_i -= 1

            if rarity_i in used_rarities:
                continue

            used_rarities.add(rarity_i)
            amount = max(1, round(base_amount * variation))

            if amount > num_max:
                continue

            bounties.append({"id": 2, "progress": 0, "cat_type": rarity, "amount": amount, "desc": f"Catch {amount} cats of {rarity} rarity and above"})
        elif bounty_type == "any":
            if any(b["id"] == 0 for b in bounties):
                continue

            amount = max(1, round(avg_cats_needed * variation / 2))

            if amount > num_max:
                continue

            bounties.append({"id": 0, "progress": 0, "cat_type": "", "amount": amount, "desc": f"Catch {amount} cats of any kind"})
        else:
            available_types = [cat for cat in cattypes if cat not in used_types]
            if not available_types:
                continue

            available_types1 = available_types.copy()
            for i in available_types:
                cat_type = random.choices(available_types1)[0]
                prob = type_dict[cat_type] / sum(type_dict.values())
                base_amount = avg_cats_needed * prob
                available_types1.remove(cat_type)
                if base_amount > 0.8:
                    break

            amount = max(1, round(base_amount * variation))

            if amount > num_max:
                continue

            used_types.add(cat_type)
            bounties.append(
                {
                    "id": 1,
                    "progress": 0,
                    "cat_type": cat_type,
                    "amount": amount,
                    "desc": f"Catch {amount} {get_emoji(cat_type.lower() + 'cat')} cat{'s' if amount > 1 else ''}",
                }
            )

    return bounties
