# Dashboard - Web dashboard for Cattito server management
# Copyright (C) 2026 Lia Milenakos & Cattito Contributors

import asyncio
import logging
import os
from pathlib import Path

import aiohttp
from aiohttp import web
from jinja2 import Environment, FileSystemLoader, select_autoescape

import database
import dashboard.database as db
import dashboard.config as config
import dashboard_routes

logger = logging.getLogger("dashboard")

template_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(['html', 'xml'])
)


def render(name: str, **ctx) -> str:
    ctx.setdefault('user', None)
    ctx.setdefault('error', None)
    ctx.setdefault('success', None)
    return template_env.get_template(name).render(**ctx)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] dashboard: %(message)s",
        datefmt="%H:%M:%S"
    )

    await database.connect()
    await db.connect()
    await db.init_tables()

    app = aiohttp.web.Application()

    async def async_render(request: web.Request, name: str, **ctx) -> str:
        return render(name, **ctx)

    app['render'] = async_render

    app.router.add_get("/", dashboard_routes.home)
    app.router.add_get("/login", dashboard_routes.login)
    app.router.add_get("/callback", dashboard_routes.callback)
    app.router.add_get("/logout", dashboard_routes.logout)
    app.router.add_get("/servers", dashboard_routes.servers)
    app.router.add_get("/guild/{guild_id}", dashboard_routes.guild)
    app.router.add_post("/guild/{guild_id}", dashboard_routes.guild)
    app.router.add_get("/guild/{guild_id}/users", dashboard_routes.guild_users)
    app.router.add_get("/guild/{guild_id}/cats", dashboard_routes.guild_cats)
    app.router.add_get("/guild/{guild_id}/channels", dashboard_routes.guild_channels)
    app.router.add_get("/api/servers", dashboard_routes.api_servers)
    app.router.add_get("/api/guild/{guild_id}", dashboard_routes.api_guild)
    app.router.add_post("/api/guild/{guild_id}", dashboard_routes.api_guild_post)

    config.bot = None

    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "5000"))

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Dashboard started on http://{host}:{port}")
    logger.warning("Note: Bot is not running. Server permission checks will fail.")


if __name__ == "__main__":
    asyncio.run(main())