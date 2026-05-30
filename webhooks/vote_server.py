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

import datetime, hashlib, hmac, json, logging, math, time
from aiohttp import web
import config
from core.utils import get_emoji, fetch_dm_channel, get_streak_reward
from database import User


async def recieve_vote(request):
    signature = request.headers.get("x-topgg-signature", "")
    try:
        signature_parts = {i.split("=")[0]: i.split("=")[1] for i in signature.split(",")}
        raw_body = await request.text()  # get plain text
        body = signature_parts.get("t", "") + "." + raw_body  # plain string concatenation
        key = config.WEBHOOK_VERIFY  # should also be plain string
        # HMAC on plain string
        computed_hmac = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()

        if computed_hmac != signature_parts.get("v1", ""):
            debug_info = (
                f"Signature verification failed!\n"
                f"Header: {signature}\n"
                f"Parsed parts: {signature_parts}\n"
                f"Raw body: {raw_body}\n"
                f"Computed HMAC: {computed_hmac}\n"
                f"Received HMAC: {signature_parts.get('v1', '')}"
            )
            print(debug_info)
            return web.Response(text=debug_info, status=403)

    except Exception as e:
        debug_info = (
            f"Exception during signature check: {e}\n"
            f"Header: {signature}\n"
            f"Raw body: {await request.text()}"
        )
        print(debug_info)
        return web.Response(text=debug_info, status=403)

    request_data = json.loads(raw_body)["data"]

    user = await User.get_or_create(user_id=int(request_data["user"]["platform_id"]))
    created_at = datetime.datetime.fromisoformat(request_data.get("created_at", datetime.datetime.utcnow().isoformat())).timestamp()


    # Determine streak extension
    if user.vote_streak < 10:
        extend_time = 24
    elif user.vote_streak < 20:
        extend_time = 36
    elif user.vote_streak < 50:
        extend_time = 48
    elif user.vote_streak < 100:
        extend_time = 60
    else:
        extend_time = 72

    user.reminder_vote = 1
    user.total_votes += 1
    freeze_note = ""

    if user.vote_time_topgg + extend_time * 3600 <= created_at:
        if user.streak_freezes < 1:
            if user.max_vote_streak < user.vote_streak:
                user.max_vote_streak = user.vote_streak
            user.vote_streak = 1
        else:
            user.vote_streak += 1
            user.streak_freezes -= 1
            freeze_note = "\n🧊 Streak Freeze Used!"
    else:
        user.vote_streak += 1

    user.vote_time_topgg = created_at

    try:
        channeley = await fetch_dm_channel(user)

        if user.vote_streak == 1:
            streak_progress = "🟦⬛⬛⬛⬛⬛⬛⬛⬛⬛\n⬆️"
        else:
            streak_progress = ""
            if user.vote_streak > 0:
                streak_progress += get_streak_reward(user.vote_streak - 1)["done_emoji"]
            streak_progress += get_streak_reward(user.vote_streak)["done_emoji"]

            for i in range(user.vote_streak + 1, user.vote_streak + 9):
                streak_progress += get_streak_reward(i)["emoji"]

            streak_progress += f"\n{get_emoji('empty')}⬆️"

        special_reward = math.ceil(user.vote_streak / 25) * 25
        if special_reward not in range(user.vote_streak, user.vote_streak + 9):
            streak_progress += f"\nNext Special Reward: {get_streak_reward(special_reward)['emoji']} at {special_reward} streak"

        streak_top_position = await User.count("vote_streak > $1", user.vote_streak) + 1
        top_text = f" (top #{streak_top_position}!)" if streak_top_position < 1000 else ""

        await channeley.send(
            "\n".join(
                [
                    "Thanks for voting! To claim your rewards, run `/battlepass` in every server you want.",
                    f"You can vote again <t:{int(created_at) + 43200}:R>.",
                    "",
                    f":fire: **Streak:** {user.vote_streak:,}{top_text} expires <t:{int(created_at) + extend_time * 3600}:R>{freeze_note}",
                    f"{streak_progress}",
                ]
            )
        )

        logging.debug("User voted, streak %d", user.vote_streak)
    except Exception:
        pass

    await user.save()
    return web.Response(text="ok", status=200)


async def check_supporter(request):
    if request.headers.get("authorization", "") != config.WEBHOOK_VERIFY:
        return web.Response(text="bad", status=403)
    request_json = await request.json()

    user = await User.get_or_create(user_id=int(request_json["user"]))
    return web.Response(text="1" if user.premium else "0", status=200)


async def uptime_handler(request):
    return web.Response(text="OK", status=200)
