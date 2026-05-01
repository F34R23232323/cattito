# Cattito Dashboard - A web dashboard for server management
# Copyright (C) 2026 Lia Milenakos & Cattito Contributors

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from typing import Optional

import aiohttp
import asyncpg
import discord
from aiohttp import web
from aiohttp.web import json_response
from jinja2 import BaseLoader, Environment

import catpg
import config
import database
from database import Channel, Profile, Server, User

logger = logging.getLogger("dashboard")

DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))

CLIENT_ID = os.getenv("DASHBOARD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DASHBOARD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DASHBOARD_REDIRECT_URI", "http://localhost:5000/callback")
SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", secrets.token_hex(32))

SCOPES = "identify guilds guilds.members.read"

cat_types = [
    "Fine", "Snacc", "Nice", "Good", "Rare", "Wild", "Kittuh", "Baby", "Epic", "Sus",
    "Water", "Brave", "Unknown", "Rickroll", "Reverse", "Superior", "Trash", "Legendary",
    "Bloodmoon", "Mythic", "8bit", "Corrupt", "Professor", "Divine", "Space", "Real",
    "Ultimate", "eGirl", "eBoy", "Snacc", "Kittuh"
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cattito Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f14; color: #fff; min-height: 100vh; }
        header { background: #1a1a24; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2a2a3a; }
        .logo { font-size: 1.5rem; font-weight: bold; color: #f5a623; }
        .userinfo { display: flex; align-items: center; gap: 1rem; }
        .userinfo img { width: 32px; height: 32px; border-radius: 50%; }
        main { padding: 2rem; max-width: 1200px; margin: 0 auto; }
        .card { background: #1a1a24; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #2a2a3a; }
        .server-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }
        .server-card { background: #1a1a24; border: 1px solid #2a2a3a; border-radius: 12px; padding: 1.5rem; transition: all 0.2s; cursor: pointer; }
        .server-card:hover { border-color: #f5a623; transform: translateY(-2px); }
        .server-icon { width: 48px; height: 48px; border-radius: 12px; margin-bottom: 1rem; }
        .server-name { font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem; }
        .no-access { opacity: 0.5; }
        .tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 1px solid #2a2a3a; padding-bottom: 0.5rem; }
        .tab { padding: 0.75rem 1.5rem; border-radius: 8px; background: transparent; border: none; color: #888; cursor: pointer; transition: all 0.2s; }
        .tab.active { background: #f5a623; color: #0f0f14; font-weight: 600; }
        .form-group { margin-bottom: 1rem; }
        label { display: block; margin-bottom: 0.5rem; color: #888; }
        input, select, textarea { width: 100%; padding: 0.75rem; background: #0f0f14; border: 1px solid #2a2a3a; border-radius: 8px; color: #fff; font-size: 1rem; }
        input:focus, select:focus, textarea:focus { outline: none; border-color: #f5a623; }
        button { background: #f5a623; color: #0f0f14; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
        button:hover { background: #e69512; }
        button.secondary { background: #2a2a3a; color: #fff; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 1rem; }
        .stat { background: #0f0f14; padding: 1rem; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 1.5rem; font-weight: bold; color: #f5a623; }
        .stat-label { font-size: 0.875rem; color: #888; margin-top: 0.25rem; }
        .error { background: #2a1a1a; border: 1px solid #4a2a2a; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; color: #ff6b6b; }
        .success { background: #1a2a1a; border: 1px solid #2a4a2a; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; color: #6bff6b; }
        .empty { text-align: center; padding: 3rem; color: #888; }
        .login-btn { background: #5865F2; color: #fff; }
        .login-btn:hover { background: #4752c4; }
    </style>
</head>
<body>
    <header>
        <div class="logo">🐱 Cattito Dashboard</div>
        {% if user %}
        <div class="userinfo">
            <span>{{ user.username }}</span>
            {% if user.avatar %}
            <img src="https://cdn.discordapp.com/avatars/{{ user.user_id }}/{{ user.avatar }}.png" alt="">
            {% endif %}
        </div>
        {% endif %}
    </header>
    <main>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        {% if success %}
        <div class="success">{{ success }}</div>
        {% endif %}
        
        {% block content %}{% endblock %}
    </main>
</body>
</html>
"""

SERVERS_TEMPLATE = """
{% extends base_template %}
{% block content %}
<div class="card">
    <h2 style="margin-bottom: 1rem;">Select a Server</h2>
    <p style="color: #888; margin-bottom: 1.5rem;">You need <strong>Manage Server</strong> permission to access a server.</p>
    
    {% if servers %}
    <div class="server-grid">
        {% for guild in servers %}
        <a href="/guild/{{ guild.id }}" {% if not guild.has_access %}class="server-card no-access"{% else %}class="server-card"{% endif %}>
            {% if guild.icon %}
            <img src="https://cdn.discordapp.com/icons/{{ guild.id }}/{{ guild.icon }}.png" class="server-icon">
            {% else %}
            <div class="server-icon" style="background: #f5a623; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">🐱</div>
            {% endif %}
            <div class="server-name">{{ guild.name }}</div>
            {% if not guild.has_access %}
            <div style="color: #ff6b6b; font-size: 0.875rem;">❌ No access</div>
            {% else %}
            <div style="color: #6bff6b; font-size: 0.875rem;">✓ Manage Server</div>
            {% endif %}
        </a>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty">No servers found. Make sure the bot is in your servers!</div>
    {% endif %}
</div>
{% endblock %}
"""

GUILD_TEMPLATE = """
{% extends base_template %}
{% block content %}
<div class="tabs">
    <a href="/guild/{{ guild_id }}" class="tab {% if active_tab == 'settings' %}active{% endif %}">Settings</a>
    <a href="/guild/{{ guild_id }}/users" class="tab {% if active_tab == 'users' %}active{% endif %}">Users</a>
    <a href="/guild/{{ guild_id }}/cats" class="tab {% if active_tab == 'cats' %}active{% endif %}">Cats</a>
    <a href="/guild/{{ guild_id }}/channels" class="tab {% if active_tab == 'channels' %}active{% endif %}">Channels</a>
</div>

{% if active_tab == 'settings' %}
<div class="card">
    <h2 style="margin-bottom: 1rem;">Server Settings</h2>
    <form method="post">
        <div class="form-group">
            <label>React to catches</label>
            <select name="do_reactions">
                <option value="true" {% if server.do_reactions %}selected{% endif %}>Enabled</option>
                <option value="false" {% if not server.do_reactions %}selected{% endif %}>Disabled</option>
            </select>
        </div>
        <button type="submit">Save Settings</button>
    </form>
</div>
{% elif active_tab == 'users' %}
<div class="card">
    <h2 style="margin-bottom: 1rem;">Server Users</h2>
    <p style="color: #888; margin-bottom: 1rem;">Top collectors in this server</p>
    
    {% if users %}
    <div class="server-grid">
        {% for u in users %}
        <div class="server-card">
            {% if u.avatar %}
            <img src="https://cdn.discordapp.com/avatars/{{ u.user_id }}/{{ u.avatar }}.png" class="server-icon">
            {% else %}
            <div class="server-icon" style="background: #6E593C; display: flex; align-items: center; justify-content: center;">🐱</div>
            {% endif %}
            <div class="server-name">{{ u.global_name or u.username }}</div>
            <div style="color: #888;">Total: {{ u.total_cats }} cats</div>
            <div style="color: #888;">Level: {{ u.catnip_level }}</div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty">No users found in this server</div>
    {% endif %}
</div>
{% elif active_tab == 'cats' %}
<div class="card">
    <h2 style="margin-bottom: 1rem;">Cat Statistics</h2>
    
    <div class="stats-grid">
        {% for cat in cat_stats %}
        <div class="stat">
            <div class="stat-value">{{ cat.count }}</div>
            <div class="stat-label">{{ cat.type }}</div>
        </div>
        {% endfor %}
    </div>
</div>
{% elif active_tab == 'channels' %}
<div class="card">
    <h2 style="margin-bottom: 1rem;">Setup Channels</h2>
    
    {% if channels %}
    <div class="server-grid">
        {% for ch in channels %}
        <div class="server-card">
            <div class="server-name">#{{ ch.channel_name }}</div>
            <div style="color: #888;">Spawn time: {{ ch.spawn_times_min }}-{{ ch.spawn_times_max }}s</div>
            <div style="color: #888;">Type: {{ ch.cattype or 'random' }}</div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty">No setup channels in this server</div>
    {% endif %}
</div>
{% endif %}
{% endblock %}
"""

LOGIN_TEMPLATE = """
{% extends base_template %}
{% block content %}
<div class="card" style="max-width: 400px; margin: 3rem auto; text-align: center;">
    <h2 style="margin-bottom: 1rem;">Login with Discord</h2>
    <p style="color: #888; margin-bottom: 2rem;">Sign in to manage your servers</p>
    <a href="/login"><button class="login-btn">Login with Discord</button></a>
</div>
{% endblock %}
"""

ERROR_404 = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>404 - Not Found</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f14; color: #fff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .container { text-align: center; }
        h1 { font-size: 6rem; margin: 0; color: #f5a623; }
        p { color: #888; margin: 1rem 0; }
        a { color: #f5a623; }
    </style>
</head>
<body>
    <div class="container">
        <h1>404</h1>
        <p>Page not found</p>
        <a href="/">Go back home</a>
    </div>
</body>
</html>
"""

class DashboardDB:
    def __init__(self):
        self.pool = None

    async def connect(self, **kwargs):
        self.pool = await asyncpg.create_pool(**kwargs)

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    avatar TEXT,
                    global_name TEXT,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL DEFAULT '',
                    created_at DOUBLE PRECISION NOT NULL,
                    expires_at DOUBLE PRECISION NOT NULL,
                    guilds_json TEXT NOT NULL DEFAULT '[]'
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON dashboard_sessions(user_id)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_oauth_state (
                    state TEXT PRIMARY KEY,
                    expires_at DOUBLE PRECISION NOT NULL
                )
            """)

    async def get_session(self, session_id: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM dashboard_sessions WHERE session_id = $1 AND expires_at > $2",
                session_id, time.time()
            )
            if row:
                return dict(row)
        return None

    async def save_session(self, session_id: str, user_id: int, username: str, avatar: Optional[str], 
                       global_name: Optional[str], access_token: str, refresh_token: str, guilds: list):
        now = time.time()
        expires_at = now + 86400 * 30  # 30 days
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO dashboard_sessions (session_id, user_id, username, avatar, global_name, access_token, refresh_token, created_at, expires_at, guilds_json)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (session_id) DO UPDATE SET
                    username = $3, avatar = $4, global_name = $5, access_token = $6, refresh_token = $7, 
                    expires_at = $9, guilds_json = $10
            """, session_id, user_id, username, avatar, global_name, access_token, refresh_token, now, expires_at, json.dumps(guilds))

    async def delete_session(self, session_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM dashboard_sessions WHERE session_id = $1", session_id)

    async def save_oauth_state(self, state: str):
        expires_at = time.time() + 600  # 10 minutes
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO dashboard_oauth_state (state, expires_at) VALUES ($1, $2) ON CONFLICT (state) DO UPDATE SET expires_at = $2",
                state, expires_at
            )

    async def get_oauth_state(self, state: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM dashboard_oauth_state WHERE state = $1 AND expires_at > $2",
                state, time.time()
            )
            return row is not None

    async def delete_oauth_state(self, state: str):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM dashboard_oauth_state WHERE state = $1", state)


class TemplateLoader(BaseLoader):
    def get_source(self, environment, template):
        return HTML_TEMPLATE, template, lambda: True


jinja_env = Environment(loader=TemplateLoader())


class DashboardServer:
    def __init__(self):
        self.app = web.Application()
        self.db = DashboardDB()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.home)
        self.app.router.add_get("/login", self.login)
        self.app.router.add_get("/callback", self.callback)
        self.app.router.add_get("/logout", self.logout)
        self.app.router.add_get("/servers", self.servers)
        self.app.router.add_get("/guild/{guild_id}", self.guild)
        self.app.router.add_post("/guild/{guild_id}", self.guild_post)
        self.app.router.add_get("/guild/{guild_id}/users", self.guild_users)
        self.app.router.add_get("/guild/{guild_id}/cats", self.guild_cats)
        self.app.router.add_get("/guild/{guild_id}/channels", self.guild_channels)
        self.app.router.add_get("/api/servers", self.api_servers)
        self.app.router.add_get("/api/guild/{guild_id}", self.api_guild)
        self.app.router.add_post("/api/guild/{guild_id}", self.api_guild_post)

    async def _render(self, template: str, **context) -> web.Response:
        base = HTML_TEMPLATE.replace("{% block content %}{% endblock %}", "{{ content }}")
        rendered = template.replace("{% extends base_template %}", base).replace("{{ user }}", str(context.get("user", "")))
        
        context.setdefault("user", None)
        context.setdefault("error", None)
        context.setdefault("success", None)
        
        html = HTML_TEMPLATE
        
        if "{% extends base_template %}" in template:
            content = template.replace("{% extends base_template %}", "").replace("{% block content %}", "").replace("{% endblock %}", "")
            html = HTML_TEMPLATE.replace("{% block content %}{% endblock %}", content)
        
        for key, value in context.items():
            html = html.replace("{{ " + key + " }}", str(value))
        
        return web.Response(text=html, content_type="text/html")

    def _get_session(self, request: web.Request) -> Optional[dict]:
        session_cookie = request.cookies.get("session")
        if not session_cookie:
            return None
        
        return asyncio.run(self.db.get_session(session_cookie.value))

    async def _check_manage_guild(self, user_id: int, guild_id: int) -> bool:
        """Check if user has Manage Server permission in the guild"""
        import config
        if not hasattr(config, 'bot') or config.bot is None:
            return False
        
        guild = config.bot.get_guild(guild_id)
        if not guild:
            return False
        
        member = guild.get_member(user_id)
        if not member:
            return False
        
        return member.guild_permissions.manage_guild

    async def home(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        
        if not session:
            return await self._render(LOGIN_TEMPLATE)
        
        return web.HTTPFound(location="/servers")

    async def login(self, request: web.Request) -> web.Response:
        state = secrets.token_urlsafe(32)
        await self.db.save_oauth_state(state)
        
        auth_url = (
            f"https://discord.com/api/oauth2/authorize"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&response_type=code"
            f"&scope={SCOPES}"
            f"&state={state}"
        )
        return web.HTTPFound(location=auth_url)

    async def callback(self, request: web.Request) -> web.Response:
        code = request.query.get("code")
        state = request.query.get("state")
        error = request.query.get("error")
        
        if error:
            return await self._render(LOGIN_TEMPLATE, error="Authorization failed")
        
        if not code or not state:
            return await self._render(LOGIN_TEMPLATE, error="Missing authorization code")
        
        if not await self.db.get_oauth_state(state):
            return await self._render(LOGIN_TEMPLATE, error="State expired or invalid")
        
        await self.db.delete_oauth_state(state)
        
        async with aiohttp.ClientSession() as session:
            token_data = {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            }
            
            async with session.post("https://discord.com/api/oauth2/token", data=token_data) as resp:
                if resp.status != 200:
                    return await self._render(LOGIN_TEMPLATE, error="Failed to exchange code for token")
                
                tokens = await resp.json()
                access_token = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token", "")
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get("https://discord.com/api/users/@me", headers=headers) as resp:
                if resp.status != 200:
                    return await self._render(LOGIN_TEMPLATE, error="Failed to get user info")
                
                user_data = await resp.json()
                user_id = int(user_data["id"])
                username = user_data.get("username", "")
                avatar = user_data.get("avatar")
                global_name = user_data.get("global_name")
            
            async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as resp:
                if resp.status != 200:
                    return await self._render(LOGIN_TEMPLATE, error="Failed to get guilds")
                
                guilds_data = await resp.json()
                guilds = [{"id": g["id"], "name": g["name"], "icon": g.get("icon")} for g in guilds_data]
        
        session_id = secrets.token_urlsafe(32)
        await self.db.save_session(
            session_id, user_id, username, avatar, global_name,
            access_token, refresh_token, guilds
        )
        
        response = web.HTTPFound(location="/servers")
        response.set_cookie("session", session_id, max_age=86400*30, httponly=True, samesite="lax")
        return response

    async def logout(self, request: web.Request) -> web.Response:
        session_cookie = request.cookies.get("session")
        if session_cookie:
            await self.db.delete_session(session_cookie.value)
        
        response = web.HTTPFound(location="/")
        response.del_cookie("session")
        return response

    async def servers(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        if not session:
            return web.HTTPFound(location="/login")
        
        import config
        bot = getattr(config, 'bot', None)
        if not bot:
            return await self._render(SERVERS_TEMPLATE, user=session, servers=[], error="Bot not connected")
        
        guilds_data = json.loads(session.get("guilds_json", "[]"))
        
        servers = []
        for g in guilds_data:
            guild_id = int(g["id"])
            has_access = await self._check_manage_guild(session["user_id"], guild_id)
            servers.append({
                "id": g["id"],
                "name": g["name"],
                "icon": g.get("icon"),
                "has_access": has_access
            })
        
        return await self._render(SERVERS_TEMPLATE, user=session, servers=servers)

    async def guild(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        if not session:
            return web.HTTPFound(location="/login")
        
        guild_id = int(request.match_info["guild_id"])
        
        has_access = await self._check_manage_guild(session["user_id"], guild_id)
        if not has_access:
            return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, error="You don't have permission to manage this server")
        
        server = await Server.get_or_none(server_id=guild_id)
        if not server:
            server = await Server.create(server_id=guild_id, do_reactions=True)
        
        if request.method == "POST":
            do_reactions = (await request.post()).get("do_reactions", "true") == "true"
            server.do_reactions = do_reactions
            await server.save()
            return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, server=server, active_tab="settings", success="Settings saved!")
        
        return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, server=server, active_tab="settings")

    async def guild_post(self, request: web.Request) -> web.Response:
        return await self.guild(request)

    async def guild_users(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        if not session:
            return web.HTTPFound(location="/login")
        
        guild_id = int(request.match_info["guild_id"])
        
        has_access = await self._check_manage_guild(session["user_id"], guild_id)
        if not has_access:
            return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, error="You don't have permission to manage this server")
        
        import config
        bot = getattr(config, 'bot', None)
        
        profiles = await Profile.collect(f"guild_id = $1 ORDER BY (cats + cat_Fine + cat_Snacc + cat_Nice + cat_Good + cat_Rare + cat_Wild + cat_Kittuh + cat_Baby + cat_Epic + cat_Sus + cat_Water + cat_Brave + cat_Unknown + cat_Rickroll + cat_Reverse + cat_Superior + cat_Trash + cat_Legendary + cat_Bloodmoon + cat_Mythic + cat_8bit + cat_Corrupt + cat_Professor + cat_Divine + cat_Space + cat_Real + cat_Ultimate + cat_eGirl + cat_eBoy) DESC LIMIT 50", guild_id)
        
        users = []
        for p in profiles:
            user = await User.get_or_none(user_id=p.user_id)
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
        
        return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, users=users, active_tab="users")

    async def guild_cats(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        if not session:
            return web.HTTPFound(location="/login")
        
        guild_id = int(request.match_info["guild_id"])
        
        has_access = await self._check_manage_guild(session["user_id"], guild_id)
        if not has_access:
            return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, error="You don't have permission to manage this server")
        
        cat_stats = []
        for cat_type in cat_types:
            count = await Profile.sum(f'"cat_{cat_type}"', f"guild_id = $1", guild_id)
            if count:
                cat_stats.append({"type": cat_type, "count": count})
        
        return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, cat_stats=cat_stats, active_tab="cats")

    async def guild_channels(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        if not session:
            return web.HTTPFound(location="/login")
        
        guild_id = int(request.match_info["guild_id"])
        
        has_access = await self._check_manage_guild(session["user_id"], guild_id)
        if not has_access:
            return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, error="You don't have permission to manage this server")
        
        import config
        bot = getattr(config, 'bot', None)
        
        channels = await Channel.collect("channel_id > 0", guild_id)
        
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
        
        return await self._render(GUILD_TEMPLATE, user=session, guild_id=guild_id, channels=channel_list, active_tab="channels")

    async def api_servers(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        if not session:
            return json_response({"error": "Not logged in"}, status=401)
        
        import config
        bot = getattr(config, 'bot', None)
        if not bot:
            return json_response({"error": "Bot not connected"}, status=500)
        
        guilds_data = json.loads(session.get("guilds_json", "[]"))
        
        servers = []
        for g in guilds_data:
            guild_id = int(g["id"])
            has_access = await self._check_manage_guild(session["user_id"], guild_id)
            if has_access:
                server = await Server.get_or_none(server_id=guild_id)
                servers.append({
                    "id": str(g["id"]),
                    "name": g["name"],
                    "icon": g.get("icon"),
                    "do_reactions": server.do_reactions if server else True
                })
        
        return json_response({"servers": servers})

    async def api_guild(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        if not session:
            return json_response({"error": "Not logged in"}, status=401)
        
        guild_id = int(request.match_info["guild_id"])
        
        has_access = await self._check_manage_guild(session["user_id"], guild_id)
        if not has_access:
            return json_response({"error": "Permission denied"}, status=403)
        
        server = await Server.get_or_none(server_id=guild_id)
        if not server:
            server = {"server_id": guild_id, "do_reactions": True}
        
        return json_response({
            "server_id": str(guild_id),
            "do_reactions": server.do_reactions if hasattr(server, 'do_reactions') else True
        })

    async def api_guild_post(self, request: web.Request) -> web.Response:
        session = await self._get_session(request)
        if not session:
            return json_response({"error": "Not logged in"}, status=401)
        
        guild_id = int(request.match_info["guild_id"])
        
        has_access = await self._check_manage_guild(session["user_id"], guild_id)
        if not has_access:
            return json_response({"error": "Permission denied"}, status=403)
        
        try:
            data = await request.json()
        except:
            data = {}
        
        server = await Server.get_or_create(server_id=guild_id)
        if "do_reactions" in data:
            server.do_reactions = bool(data["do_reactions"])
        await server.save()
        
        return json_response({"success": True, "server_id": str(guild_id)})

    async def start(self):
        import config as bot_config
        import main as bot_main
        
        await self.db.connect(
            user="cat_bot",
            password="meow",
            database="cat_bot",
            host="127.0.0.1",
            port=5432
        )
        await self.db.create_tables()
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, DASHBOARD_HOST, DASHBOARD_PORT)
        await site.start()
        
        logger.info(f"Dashboard started on http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")


async def start_dashboard():
    dashboard = DashboardServer()
    await dashboard.start()


if __name__ == "__main__":
    asyncio.run(start_dashboard())