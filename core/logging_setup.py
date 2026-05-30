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
import logging
import os
import time

import aiohttp
import discord

import config
import shared


async def _post_webhook(webhook_url: str, embed: discord.Embed):
    """POST an embed to a Discord webhook URL."""
    payload = {"embeds": [embed.to_dict()]}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                logging.warning(f"Webhook post returned {resp.status}: {text[:200]}")


async def log_guild_join(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_GUILD_JOIN", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_guild_join webhook failed: {e}")


async def log_guild_leave(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_GUILD_LEAVE", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_guild_leave webhook failed: {e}")


async def log_command(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_COMMANDS", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_command webhook failed: {e}")


async def log_error(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_ERRORS", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_error webhook failed: {e}")


async def log_rain(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_RAIN", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_rain webhook failed: {e}")


async def log_catch(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_CATCH", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_catch webhook failed: {e}")


async def log_dev(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_DEV", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_dev webhook failed: {e}")


async def log_prefix(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_PREFIX", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_prefix webhook failed: {e}")


async def log_uptime(embed: discord.Embed):
    url = getattr(config, "LOG_WEBHOOK_UPTIME", None) or getattr(config, "LOG_WEBHOOK", None)
    if url:
        try:
            await _post_webhook(url, embed)
        except Exception as e:
            logging.warning(f"log_uptime webhook failed: {e}")


class WebhookLogHandler(logging.Handler):
    """Buffers log records and flushes them to a Discord webhook in batches."""

    FLUSH_INTERVAL = 5.0
    MIN_POST_GAP = 2.0
    MAX_CHARS = 1900

    def __init__(self):
        super().__init__()
        self._buffer: list[str] = []
        self._lock = asyncio.Lock()
        self._last_post = 0.0
        self._task: asyncio.Task | None = None

    def emit(self, record: logging.LogRecord):
        try:
            line = self.format(record)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(self._buffer.append, line)
            except RuntimeError:
                pass
        except Exception:
            pass

    def start(self, loop: asyncio.AbstractEventLoop):
        self._task = loop.create_task(self._flush_loop())

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(self.FLUSH_INTERVAL)
            await self._flush()

    async def _flush(self):
        url = getattr(config, "LOG_WEBHOOK_CONSOLE", None) or getattr(config, "LOG_WEBHOOK", None)
        if not url:
            self._buffer.clear()
            return

        async with self._lock:
            if not self._buffer:
                return

            since_last = asyncio.get_event_loop().time() - self._last_post
            if since_last < self.MIN_POST_GAP:
                await asyncio.sleep(self.MIN_POST_GAP - since_last)

            lines = self._buffer.copy()
            self._buffer.clear()

        chunks: list[str] = []
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > self.MAX_CHARS:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = (current + "\n" + line).lstrip("\n")
        if current:
            chunks.append(current)

        for chunk in chunks:
            try:
                embed = discord.Embed(
                    title="Console Log",
                    description=f"```\n{chunk}\n```",
                    color=0x2b2d31,
                    timestamp=discord.utils.utcnow(),
                )
                await _post_webhook(url, embed)
                self._last_post = asyncio.get_event_loop().time()
                if len(chunks) > 1:
                    await asyncio.sleep(self.MIN_POST_GAP)
            except Exception as e:
                logging.getLogger("webhookhandler").warning(f"Console webhook flush failed: {e}")


_webhook_log_handler = WebhookLogHandler()
_webhook_log_handler.setFormatter(
    logging.Formatter(f"%(asctime)s [%(levelname)s] [PID {os.getpid()}] %(name)s: %(message)s", datefmt="%H:%M:%S")
)
