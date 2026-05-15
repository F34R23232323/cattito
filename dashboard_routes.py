# Dashboard routes

import json
import secrets
from typing import Callable

import aiohttp
from aiohttp import web

import dashboard.config as config
import dashboard.database as db
import dashboard.oauth as oauth
import database


cat_types = [
    "Fine", "Snacc", "Nice", "Good", "Rare", "Wild", "Kittuh", "Baby", "Epic", "Sus",
    "Water", "Brave", "Unknown", "Rickroll", "Reverse", "Superior", "Trash", "Legendary",
    "Bloodmoon", "Mythic", "8bit", "Corrupt", "Professor", "Divine", "Space", "Real",
    "Ultimate", "eGirl", "eBoy"
]

# Columns that actually exist in the profile table (schema-verified).
# cat_8bit has no quotes in DB; all others are quoted identifiers.
db_cat_types = [
    "Fine", "Nice", "Good", "Rare", "Wild", "Baby", "Epic", "Sus",
    "Brave", "Rickroll", "Reverse", "Superior", "Trash", "Legendary",
    "Mythic", "8bit", "Corrupt", "Professor", "Divine", "Real",
    "Ultimate", "eGirl", "Princess", "Rainbow", "Angel",
]


async def render(request: web.Request, name: str, **ctx) -> str:
    render_func = request.app.get('render')
    if render_func:
        return render_func(name, **ctx)
    from pathlib import Path
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "dashboard" / "templates"))
    return env.get_template(name).render(**ctx)


async def check_session_async(request: web.Request) -> dict:
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        return None
    return await db.get_session(session_cookie)


MANAGE_GUILD_PERMISSION = 0x20


async def bot_in_guild(guild_id: int) -> bool:
    """Return True only if the bot is present in this guild."""
    bot = config.bot
    if bot:
        return bot.get_guild(guild_id) is not None
    # Bot not running — use DB as proxy: if a server row exists the bot was set up there
    server = await database.Server.get_or_none(server_id=guild_id)
    return server is not None


async def check_manage_guild(user_id: int, guild_id: int, session: dict = None) -> bool:
    """Check if user has Manage Server permission AND the bot is in the guild.
    Uses the live bot cache if available, otherwise falls back to the
    OAuth guild permissions bitmask stored in the session."""
    # Bot must be present first
    if not await bot_in_guild(guild_id):
        return False

    bot = config.bot
    if bot:
        guild = bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
            if member:
                return member.guild_permissions.manage_guild

    # Bot not available or guild/member not cached — use OAuth bitmask fallback
    if session:
        guilds_data = json.loads(session.get("guilds_json", "[]"))
        for g in guilds_data:
            if int(g["id"]) == guild_id:
                perms = int(g.get("permissions", 0))
                # ADMINISTRATOR (0x8) implies all permissions
                return bool(perms & MANAGE_GUILD_PERMISSION) or bool(perms & 0x8)

    return False


async def home(request: web.Request) -> web.Response:
    session = await check_session_async(request)
    
    if not session:
        return aiohttp.web.HTTPFound(location="/login")
    
    return aiohttp.web.HTTPFound(location="/servers")


async def login(request: web.Request) -> web.Response:
    state = secrets.token_urlsafe(32)
    await db.save_oauth_state(state)
    
    auth_url = oauth.get_auth_url(state)
    return aiohttp.web.HTTPFound(location=auth_url)


async def callback(request: web.Request) -> web.Response:
    code = request.query.get("code")
    state = request.query.get("state")
    
    if not code or not state:
        return web.Response(
            text=await render(request, "login.html", error="Missing authorization code"),
            content_type="text/html"
        )
    
    if not await db.get_oauth_state(state):
        return web.Response(
            text=await render(request, "login.html", error="State expired or invalid"),
            content_type="text/html"
        )
    
    await db.delete_oauth_state(state)
    
    tokens = await oauth.exchange_code(code)
    if not tokens:
        return web.Response(
            text=await render(request, "login.html", error="Failed to exchange code for token"),
            content_type="text/html"
        )
    
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token", "")
    
    user_data = await oauth.get_user(access_token)
    if not user_data:
        return web.Response(
            text=await render(request, "login.html", error="Failed to get user info"),
            content_type="text/html"
        )
    
    user_id = int(user_data["id"])
    username = user_data.get("username", "")
    avatar = user_data.get("avatar")
    global_name = user_data.get("global_name")
    
    guilds = await oauth.get_guilds(access_token)
    
    session_id = secrets.token_urlsafe(32)
    await db.save_session(
        session_id, user_id, username, avatar, global_name,
        access_token, refresh_token, guilds
    )
    
    response = aiohttp.web.HTTPFound(location="/servers")
    response.set_cookie("session", session_id, max_age=86400*30, httponly=True, samesite="lax")
    return response


async def logout(request: web.Request) -> web.Response:
    session_cookie = request.cookies.get("session")
    if session_cookie:
        await db.delete_session(session_cookie)
    
    response = aiohttp.web.HTTPFound(location="/")
    response.del_cookie("session")
    return response


async def servers(request: web.Request) -> web.Response:
    session = await check_session_async(request)
    
    if not session:
        return aiohttp.web.HTTPFound(location="/login")
    
    guilds_data = json.loads(session.get("guilds_json", "[]"))
    
    servers_list = []
    for g in guilds_data:
        guild_id = int(g["id"])
        present = await bot_in_guild(guild_id)
        has_access = False
        if present:
            has_access = await check_manage_guild(session["user_id"], guild_id, session)
        servers_list.append({
            "id": g["id"],
            "name": g["name"],
            "icon": g.get("icon"),
            "has_access": has_access,
            "bot_present": present,
        })
    
    return web.Response(
        text=await render(request, "servers.html", user=session, servers=servers_list),
        content_type="text/html"
    )


async def guild(request: web.Request) -> web.Response:
    session = await check_session_async(request)

    if not session:
        return aiohttp.web.HTTPFound(location="/login")

    guild_id = int(request.match_info["guild_id"])

    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.Response(
            text=await render(request, "guild.html", guild_id=guild_id, error="You don't have permission to manage this server"),
            content_type="text/html"
        )

    server_name = "Server"
    if config.bot:
        guild_obj = config.bot.get_guild(guild_id)
        if guild_obj:
            server_name = guild_obj.name

    if request.method == "POST":
        post_data = await request.post()
        do_reactions = post_data.get("do_reactions", "true") == "true"
        welcome_message = post_data.get("welcome_message", "")[:500]
        try:
            spawn_min = max(10, min(3600, int(post_data.get("spawn_min", 60))))
            spawn_max = max(10, min(3600, int(post_data.get("spawn_max", 600))))
            if spawn_min > spawn_max:
                spawn_min, spawn_max = spawn_max, spawn_min
        except (ValueError, TypeError):
            spawn_min, spawn_max = 60, 600

        server = await database.Server.get_or_none(server_id=guild_id)
        if not server:
            await database.Server.create(
                server_id=guild_id,
                do_reactions=do_reactions,
                welcome_message=welcome_message,
                spawn_min=spawn_min,
                spawn_max=spawn_max,
            )
            server = await database.Server.get_or_none(server_id=guild_id)
        else:
            server.do_reactions = do_reactions
            server.welcome_message = welcome_message
            server.spawn_min = spawn_min
            server.spawn_max = spawn_max
            await server.save()

        return web.Response(
            text=await render(request, "guild.html", guild_id=guild_id, server=server, server_name=server_name, active_tab="settings", success="Settings saved!"),
            content_type="text/html"
        )

    server = await database.Server.get_or_none(server_id=guild_id)
    return web.Response(
        text=await render(request, "guild.html", guild_id=guild_id, server=server, server_name=server_name, active_tab="settings"),
        content_type="text/html"
    )


async def guild_users(request: web.Request) -> web.Response:
    session = await check_session_async(request)
    
    if not session:
        return aiohttp.web.HTTPFound(location="/login")
    
    guild_id = int(request.match_info["guild_id"])
    
    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.Response(
            text=await render(request, "guild.html", guild_id=guild_id, error="You don't have permission to manage this server"),
            content_type="text/html"
        )
    
    # Build ORDER BY only from columns that exist in the DB.
    # cat_8bit has no mixed-case so needs no quoting; all others do.
    _order_cols = " + ".join(
        f"cat_8bit" if t == "8bit" else f'"cat_{t}"'
        for t in db_cat_types
    )
    profiles = await database.Profile.collect(
        f'guild_id = $1 ORDER BY ({_order_cols}) DESC LIMIT 50',
        guild_id
    )
    
    users = []
    for p in profiles:
        user = await database.User.get_or_none(user_id=p.user_id)
        total_cats = sum(
            getattr(p, "cat_8bit" if t == "8bit" else f"cat_{t}") or 0
            for t in db_cat_types
        )
        
        users.append({
            "user_id": p.user_id,
            "username": user.username if user else "",
            "global_name": user.global_name if user else "",
            "avatar": user.avatar if user else None,
            "total_cats": total_cats,
            "catnip_level": p.catnip_level or 0
        })
    
    server_name = "Server"
    if config.bot:
        guild_obj = config.bot.get_guild(guild_id)
        if guild_obj:
            server_name = guild_obj.name
    
    return web.Response(
        text=await render(request, "guild.html", guild_id=guild_id, server_name=server_name, users=users, active_tab="users"),
        content_type="text/html"
    )


async def guild_cats(request: web.Request) -> web.Response:
    session = await check_session_async(request)
    
    if not session:
        return aiohttp.web.HTTPFound(location="/login")
    
    guild_id = int(request.match_info["guild_id"])
    
    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.Response(
            text=await render(request, "guild.html", guild_id=guild_id, error="You don't have permission to manage this server"),
            content_type="text/html"
        )
    
    cat_stats = []
    for cat_type in db_cat_types:
        col = f"cat_{cat_type}"
        count = await database.Profile.sum(col, f"guild_id = $1", guild_id)
        if count:
            cat_stats.append({"type": cat_type, "count": count})
    
    server_name = "Server"
    if config.bot:
        guild_obj = config.bot.get_guild(guild_id)
        if guild_obj:
            server_name = guild_obj.name
    
    return web.Response(
        text=await render(request, "guild.html", guild_id=guild_id, server_name=server_name, cat_stats=cat_stats, active_tab="cats"),
        content_type="text/html"
    )


async def guild_channels(request: web.Request) -> web.Response:
    session = await check_session_async(request)

    if not session:
        return aiohttp.web.HTTPFound(location="/login")

    guild_id = int(request.match_info["guild_id"])

    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.Response(
            text=await render(request, "guild.html", guild_id=guild_id, error="You don't have permission to manage this server"),
            content_type="text/html"
        )

    bot = config.bot
    channel_list = []
    server_name = "Server"

    if bot:
        # Use the bot cache to find channels that belong to this guild
        guild_obj = bot.get_guild(guild_id)
        server_name = guild_obj.name if guild_obj else "Server"
        if guild_obj:
            guild_channel_ids = [c.id for c in guild_obj.channels]
            if guild_channel_ids:
                # Fetch only channels that are in this guild
                placeholders = ", ".join(f"${i+1}" for i in range(len(guild_channel_ids)))
                channels = await database.Channel.collect(
                    f"channel_id IN ({placeholders})", *guild_channel_ids
                )
                for ch in channels:
                    discord_ch = guild_obj.get_channel(ch.channel_id)
                    channel_list.append({
                        "channel_id": ch.channel_id,
                        "channel_name": discord_ch.name if discord_ch else f"Channel {ch.channel_id}",
                        "spawn_times_min": ch.spawn_times_min,
                        "spawn_times_max": ch.spawn_times_max,
                        "cattype": ch.cattype or "",
                    })
    else:
        pass  # server_name already defaulted to "Server" above

    return web.Response(
        text=await render(request, "guild.html", guild_id=guild_id, server_name=server_name, channels=channel_list, active_tab="channels"),
        content_type="text/html"
    )


async def api_channel_update(request: web.Request) -> web.Response:
    session = await check_session_async(request)

    if not session:
        return web.json_response({"error": "Not logged in"}, status=401)

    guild_id = int(request.match_info["guild_id"])
    channel_id = int(request.match_info["channel_id"])

    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.json_response({"error": "Permission denied"}, status=403)

    # Verify channel is actually in this guild
    bot = config.bot
    if bot:
        guild_obj = bot.get_guild(guild_id)
        if not guild_obj or not guild_obj.get_channel(channel_id):
            return web.json_response({"error": "Channel not in this guild"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    ch = await database.Channel.get_or_none(channel_id=channel_id)
    if not ch:
        return web.json_response({"error": "Channel not found in database"}, status=404)

    try:
        spawn_min = max(10, min(3600, int(data.get("spawn_times_min", ch.spawn_times_min))))
        spawn_max = max(10, min(3600, int(data.get("spawn_times_max", ch.spawn_times_max))))
        if spawn_min > spawn_max:
            spawn_min, spawn_max = spawn_max, spawn_min
    except (ValueError, TypeError):
        return web.json_response({"error": "Invalid spawn times"}, status=400)

    cattype = str(data.get("cattype", ch.cattype or ""))[:20]

    ch.spawn_times_min = spawn_min
    ch.spawn_times_max = spawn_max
    ch.cattype = cattype
    await ch.save()

    return web.json_response({"success": True})


async def api_user_cats_get(request: web.Request) -> web.Response:
    session = await check_session_async(request)

    if not session:
        return web.json_response({"error": "Not logged in"}, status=401)

    guild_id = int(request.match_info["guild_id"])
    target_user_id = int(request.match_info["user_id"])

    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.json_response({"error": "Permission denied"}, status=403)

    profile = await database.Profile.get_or_none(user_id=target_user_id, guild_id=guild_id)
    if not profile:
        return web.json_response({"error": "User profile not found"}, status=404)

    cats = {
        f"cat_{t}": (getattr(profile, "cat_8bit" if t == "8bit" else f"cat_{t}") or 0)
        for t in db_cat_types
    }
    return web.json_response({"cats": cats})


async def api_user_cats_update(request: web.Request) -> web.Response:
    session = await check_session_async(request)

    if not session:
        return web.json_response({"error": "Not logged in"}, status=401)

    guild_id = int(request.match_info["guild_id"])
    target_user_id = int(request.match_info["user_id"])

    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.json_response({"error": "Permission denied"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    profile = await database.Profile.get_or_none(user_id=target_user_id, guild_id=guild_id)
    if not profile:
        return web.json_response({"error": "User profile not found"}, status=404)

    updated = []
    for cat_type in db_cat_types:
        key = f"cat_{cat_type}"
        if key in data:
            try:
                val = max(0, int(data[key]))
                attr = "cat_8bit" if cat_type == "8bit" else key
                setattr(profile, attr, val)
                updated.append(key)
            except (ValueError, TypeError):
                pass

    if updated:
        await profile.save()

    return web.json_response({"success": True, "updated": updated})


async def api_servers(request: web.Request) -> web.Response:
    session = await check_session_async(request)
    
    if not session:
        return web.json_response({"error": "Not logged in"}, status=401)
    
    bot = config.bot
    guilds_data = json.loads(session.get("guilds_json", "[]"))
    
    servers = []
    for g in guilds_data:
        guild_id = int(g["id"])
        has_access = await check_manage_guild(session["user_id"], guild_id, session)
        if has_access:
            server = await database.Server.get_or_none(server_id=guild_id)
            servers.append({
                "id": str(g["id"]),
                "name": g["name"],
                "icon": g.get("icon"),
                "do_reactions": server.do_reactions if server else True
            })
    
    return web.json_response({"servers": servers})


async def api_guild(request: web.Request) -> web.Response:
    session = await check_session_async(request)
    
    if not session:
        return web.json_response({"error": "Not logged in"}, status=401)
    
    guild_id = int(request.match_info["guild_id"])
    
    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.json_response({"error": "Permission denied"}, status=403)
    
    server = await database.Server.get_or_none(server_id=guild_id)
    if not server:
        return web.json_response({
            "server_id": str(guild_id),
            "do_reactions": True
        })
    
    return web.json_response({
        "server_id": str(guild_id),
        "do_reactions": server.do_reactions if hasattr(server, 'do_reactions') else True
    })


async def api_guild_post(request: web.Request) -> web.Response:
    session = await check_session_async(request)
    
    if not session:
        return web.json_response({"error": "Not logged in"}, status=401)
    
    guild_id = int(request.match_info["guild_id"])
    
    has_access = await check_manage_guild(session["user_id"], guild_id, session)
    if not has_access:
        return web.json_response({"error": "Permission denied"}, status=403)
    
    try:
        data = await request.json()
    except:
        data = {}
    
    server, created = await database.Server.get_or_create(server_id=guild_id)
    if "do_reactions" in data:
        server.do_reactions = bool(data["do_reactions"])
    await server.save()
    
    return web.json_response({"success": True, "server_id": str(guild_id)})