# OAuth2 handling for Discord

import aiohttp
import dashboard.config as config


async def exchange_code(code: str) -> dict:
    """Exchange authorization code for access token"""
    async with aiohttp.ClientSession() as session:
        data = {
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.REDIRECT_URI,
        }

        async with session.post("https://discord.com/api/oauth2/token", data=data) as resp:
            if resp.status != 200:
                return None
            return await resp.json()


async def refresh_token(refresh_token: str) -> dict:
    """Refresh access token"""
    async with aiohttp.ClientSession() as session:
        data = {
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        async with session.post("https://discord.com/api/oauth2/token", data=data) as resp:
            if resp.status != 200:
                return None
            return await resp.json()


async def get_user(access_token: str) -> dict:
    """Get current user info"""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discord.com/api/users/@me", headers=headers) as resp:
            if resp.status != 200:
                return None
            return await resp.json()


async def get_guilds(access_token: str) -> list:
    """Get user's guilds"""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return [{"id": g["id"], "name": g["name"], "icon": g.get("icon"), "permissions": g.get("permissions", "0")} for g in data]


def get_auth_url(state: str) -> str:
    """Build OAuth2 authorization URL"""
    return (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={config.CLIENT_ID}"
        f"&redirect_uri={config.REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={config.SCOPES}"
        f"&state={state}"
    )