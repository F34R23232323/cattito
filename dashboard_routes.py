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


async def check_manage_guild(user_id: int, guild_id: int, session: dict = None) -> bool:
    """Check if user has Manage Server permission in the guild.
    Uses the live bot cache if available, otherwise falls back to the
    OAuth guild permissions bitmask stored in the session."""
    bot = config.bot
    if bot:
        guild = bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
            if member:
                return member.guild_permissions.manage_guild

    # Bot not available or guild/member not cached — use OAuth bitmask fallback
    if session:
        import json
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
        has_access = await check_manage_guild(session["user_id"], guild_id, session)
        servers_list.append({
            "id": g["id"],
            "name": g["name"],
            "icon": g.get("icon"),
            "has_access": has_access
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
    
    server = await database.Server.get_or_none(server_id=guild_id)
    if not server:
        class FakeServer:
            pass
        server = FakeServer()
        server.server_id = guild_id
        server.do_reactions = True
    
    server_name = "Server"
    if config.bot:
        guild_obj = config.bot.get_guild(guild_id)
        if guild_obj:
            server_name = guild_obj.name
    
    if request.method == "POST":
        post_data = await request.post()
        do_reactions = post_data.get("do_reactions", "true") == "true"
        
        if not await database.Server.get_or_none(server_id=guild_id):
            await database.Server.create(server_id=guild_id, do_reactions=do_reactions)
        else:
            server.do_reactions = do_reactions
            await server.save()
        
        return web.Response(
            text=await render(request, "guild.html", guild_id=guild_id, server=server, server_name=server_name, active_tab="settings", success="Settings saved!"),
            content_type="text/html"
        )
    
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
    
    profiles = await database.Profile.collect(
        f"guild_id = $1 ORDER BY (cats + cat_Fine + cat_Snacc + cat_Nice + cat_Good + cat_Rare + cat_Wild + cat_Kittuh + cat_Baby + cat_Epic + cat_Sus + cat_Water + cat_Brave + cat_Unknown + cat_Rickroll + cat_Reverse + cat_Superior + cat_Trash + cat_Legendary + cat_Bloodmoon + cat_Mythic + cat_8bit + cat_Corrupt + cat_Professor + cat_Divine + cat_Space + cat_Real + cat_Ultimate + cat_eGirl + cat_eBoy) DESC LIMIT 50",
        guild_id
    )
    
    users = []
    for p in profiles:
        user = await database.User.get_or_none(user_id=p.user_id)
        total_cats = sum([
            p.cat_Fine or 0, p.cat_Snacc or 0, p.cat_Nice or 0, p.cat_Good or 0, 
            p.cat_Rare or 0, p.cat_Wild or 0, p.cat_Kittuh or 0, p.cat_Baby or 0,
            p.cat_Epic or 0, p.cat_Sus or 0, p.cat_Water or 0, p.cat_Brave or 0,
            p.cat_Unknown or 0, p.cat_Rickroll or 0, p.cat_Reverse or 0,
            p.cat_Superior or 0, p.cat_Trash or 0, p.cat_Legendary or 0,
            p.cat_Bloodmoon or 0, p.cat_Mythic or 0, p.cat_8bit or 0,
            p.cat_Corrupt or 0, p.cat_Professor or 0, p.cat_Divine or 0,
            p.cat_Space or 0, p.cat_Real or 0, p.cat_Ultimate or 0,
            p.cat_eGirl or 0, p.cat_eBoy or 0
        ])
        
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
    for cat_type in cat_types:
        count = await database.Profile.sum(f'"cat_{cat_type}"', f"guild_id = $1", guild_id)
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
    channels = await database.Channel.collect("channel_id > 0", guild_id)
    
    channel_list = []
    for ch in channels:
        if bot:
            discord_ch = bot.get_channel(ch.channel_id)
            channel_name = discord_ch.name if discord_ch else f"Channel {ch.channel_id}"
        else:
            channel_name = f"Channel {ch.channel_id}"
        
        channel_list.append({
            "channel_id": ch.channel_id,
            "channel_name": channel_name,
            "spawn_times_min": ch.spawn_times_min,
            "spawn_times_max": ch.spawn_times_max,
            "cattype": ch.cattype
        })
    
    server_name = "Server"
    if config.bot:
        guild_obj = config.bot.get_guild(guild_id)
        if guild_obj:
            server_name = guild_obj.name
    
    return web.Response(
        text=await render(request, "guild.html", guild_id=guild_id, server_name=server_name, channels=channel_list, active_tab="channels"),
        content_type="text/html"
    )


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
    
    server = await database.Server.get_or_create(server_id=guild_id)
    if hasattr(server, 'save'):
        if "do_reactions" in data:
            server.do_reactions = bool(data["do_reactions"])
        await server.save()
    
    return web.json_response({"success": True, "server_id": str(guild_id)})